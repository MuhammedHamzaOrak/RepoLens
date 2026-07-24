from foundry_local_sdk import Configuration, FoundryLocalManager


MODEL_ALIAS = "qwen3-embedding-0.6b"
CHAT_MODEL_ALIAS = "qwen2.5-0.5b"


def _print_download_progress(progress: float) -> None:
    print(f"Download progress: {progress:.0%}")


def _ensure_model_ready(model_alias: str) -> object:
    model = FoundryLocalManager.instance.catalog.get_model(model_alias)
    if model is None:
        raise RuntimeError(f"Unable to resolve {model_alias} from Foundry Local catalog.")

    print(f"Model resolved: {model.alias} ({model.id})")
    print(f"Initial cache/load status: cached={model.is_cached}, loaded={model.is_loaded}")

    if not model.is_cached:
        print(
            f"Model {model_alias} is not cached locally yet. Downloading it now; "
            "this may take several minutes on the first run."
        )
        model.download(progress_callback=_print_download_progress)

    if not model.is_loaded:
        print(f"Loading model {model_alias} into the Foundry Local runtime...")
        model.load()

    print(
        "Model readiness check complete: "
        f"cached={model.is_cached}, loaded={model.is_loaded}"
    )
    return model


def main() -> None:
    config = Configuration(app_name="RepoLens")
    FoundryLocalManager.initialize(config)

    try:
        embedding_model = _ensure_model_ready(MODEL_ALIAS)
        embedding_client = embedding_model.get_embedding_client()
        embedding_response = embedding_client.generate_embedding("RepoLens smoke test")
        print("Embedding length:", len(embedding_response.data[0].embedding))

        chat_model = _ensure_model_ready(CHAT_MODEL_ALIAS)
        chat_client = chat_model.get_chat_client()
        completion = chat_client.complete_chat(
            [
                {"role": "system", "content": "You are a concise assistant."},
                {"role": "user", "content": "Reply with the single word: ok"},
            ]
        )
        print("Chat completion:", completion.choices[0].message.content)
    except Exception as exc:
        message = str(exc).lower()
        if "download" in message or "load" in message:
            raise RuntimeError(f"Model setup failed for {MODEL_ALIAS}: {exc}") from exc
        raise RuntimeError(f"Foundry Local inference failed for {MODEL_ALIAS}: {exc}") from exc


if __name__ == "__main__":
    main()
