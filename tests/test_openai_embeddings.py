from types import SimpleNamespace

from tiny_agent.integrations.openai_embeddings import OpenAIEmbeddingModel


class FakeEmbeddings:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        dimension = kwargs["dimensions"]
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=index, embedding=[float(index + 1)] * dimension)
                for index, _ in enumerate(kwargs["input"])
            ]
        )


def test_openai_embedding_adapter_is_provider_neutral_and_dimension_checked() -> None:
    embeddings = FakeEmbeddings()
    client = SimpleNamespace(embeddings=embeddings)
    model = OpenAIEmbeddingModel(client, dimension=3)
    assert model.embed_documents(["a", "b"]) == [[1.0, 1.0, 1.0], [2.0, 2.0, 2.0]]
    assert model.embed_query("q") == [1.0, 1.0, 1.0]
    assert embeddings.calls[0]["model"] == "text-embedding-3-small"
