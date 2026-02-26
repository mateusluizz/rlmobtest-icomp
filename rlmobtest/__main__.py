"""Main entry point for RLMobTest - RL-based Android mobile app testing."""


def main():
    """Main entry point - delegates to CLI."""
    from rlmobtest.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
