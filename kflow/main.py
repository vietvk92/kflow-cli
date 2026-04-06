"""Application entrypoint."""

from kflow.cli.app import app


def main() -> None:
    """Run the KFlow CLI."""
    app()


if __name__ == "__main__":
    main()
