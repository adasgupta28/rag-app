import json

from tests.conftest import make_pdf


def _upload(client, path, name=None):
    with open(path, "rb") as f:
        return client.post("/api/documents", files={"file": (name or path.name, f, "application/pdf")})


def _chat(client, question, conversation_id=None):
    response = client.post("/api/chat", json={"question": question, "conversation_id": conversation_id})
    assert response.status_code == 200
    events = []
    for block in response.text.strip().split("\n\n"):
        name_line, data_line = block.split("\n", 1)
        events.append((name_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))))
    return events


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["indexed_chunks"] == 0


def test_upload_ingests_and_lists_document(client, tmp_path):
    pdf = make_pdf(tmp_path / "solar.pdf", ["Solar panels convert sunlight.", "Batteries store energy."])

    response = _upload(client, pdf)
    assert response.status_code == 202
    doc_id = response.json()["id"]

    # TestClient runs background tasks before returning, so ingestion is complete here.
    doc = client.get(f"/api/documents/{doc_id}").json()
    assert doc["status"] == "ready", doc["error"]
    assert doc["page_count"] == 2
    assert doc["chunk_count"] >= 1
    assert [d["id"] for d in client.get("/api/documents").json()] == [doc_id]
    assert client.get(f"/api/documents/{doc_id}/file").headers["content-type"] == "application/pdf"


def test_duplicate_upload_rejected(client, tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf", ["Same content."])
    assert _upload(client, pdf).status_code == 202
    assert _upload(client, pdf, name="copy.pdf").status_code == 409


def test_non_pdf_rejected(client, tmp_path):
    fake = tmp_path / "notes.pdf"
    fake.write_text("not really a pdf")
    assert _upload(client, fake).status_code == 415


def test_pdf_without_text_fails_gracefully(client, tmp_path):
    pdf = make_pdf(tmp_path / "blank.pdf", [""])
    doc = client.get(f"/api/documents/{_upload(client, pdf).json()['id']}").json()
    assert doc["status"] == "failed"
    assert "OCR" in doc["error"]


def test_delete_removes_file_and_vectors(client, tmp_path, settings):
    pdf = make_pdf(tmp_path / "gone.pdf", ["Temporary document content."])
    doc_id = _upload(client, pdf).json()["id"]
    assert client.get("/api/health").json()["indexed_chunks"] > 0

    assert client.delete(f"/api/documents/{doc_id}").status_code == 204
    assert client.get(f"/api/documents/{doc_id}").status_code == 404
    assert client.get("/api/health").json()["indexed_chunks"] == 0
    assert list(settings.docs_dir.iterdir()) == []


def test_chat_retrieves_relevant_sources_and_streams(client, tmp_path, fake_llm):
    _upload(client, make_pdf(tmp_path / "pets.pdf", ["Cats sleep sixteen hours a day."]))
    _upload(client, make_pdf(tmp_path / "space.pdf", ["Mars has two moons, Phobos and Deimos."]))

    events = _chat(client, "How many moons does Mars have?")
    names = [name for name, _ in events]
    assert names[:2] == ["meta", "sources"]
    assert names[-1] == "done"

    sources = events[1][1]
    assert sources[0]["filename"] == "space.pdf"
    assert sources[0]["n"] == 1

    answer = "".join(data["text"] for name, data in events if name == "token")
    assert answer == "The answer is here [1]."
    # First turn: no query rewriting, and excerpts are in the prompt.
    assert fake_llm.complete_calls == []
    assert "Phobos" in fake_llm.stream_calls[0][-1]["content"]


def test_follow_up_uses_history_and_rewritten_query(client, tmp_path, fake_llm):
    _upload(client, make_pdf(tmp_path / "space.pdf", ["Mars has two moons, Phobos and Deimos."]))

    first = _chat(client, "Tell me about Mars")
    conversation_id = first[0][1]["conversation_id"]

    fake_llm.rewrite_to = "What are the names of the moons of Mars?"
    follow_up = _chat(client, "What are they called?", conversation_id)

    assert follow_up[0][1] == {"conversation_id": conversation_id, "query": fake_llm.rewrite_to}
    # The condense prompt saw the earlier turn, and the answer prompt includes history.
    assert "Tell me about Mars" in fake_llm.complete_calls[0][-1]["content"]
    roles = [m["role"] for m in fake_llm.stream_calls[1]]
    assert roles == ["system", "user", "assistant", "user"]

    detail = client.get(f"/api/conversations/{conversation_id}").json()
    assert detail["title"] == "Tell me about Mars"
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant", "user", "assistant"]
    assert detail["messages"][3]["rewritten_query"] == fake_llm.rewrite_to
    assert detail["messages"][3]["sources"][0]["filename"] == "space.pdf"


def test_chat_with_no_documents_still_answers(client, fake_llm):
    events = _chat(client, "Anything?")
    assert events[1] == ("sources", [])
    assert "No relevant excerpts" in fake_llm.stream_calls[0][-1]["content"]


def test_delete_conversation(client):
    conversation_id = _chat(client, "Hi")[0][1]["conversation_id"]
    assert len(client.get("/api/conversations").json()) == 1
    assert client.delete(f"/api/conversations/{conversation_id}").status_code == 204
    assert client.get("/api/conversations").json() == []
