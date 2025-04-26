"""
rooBroker main entry point.

This module serves as the primary entry point for the rooBroker application.
It routes execution to either CLI or interactive mode based on command-line arguments.
"""

import sys
from typing import NoReturn

from rooBroker import main_cli
from rooBroker import main_interactive


def main() -> NoReturn:
    """
    Main entry point for rooBroker.
    
    Routes to:
    - CLI mode if arguments are provided
    - Interactive mode if no arguments are provided
    
    Exits the program with appropriate status code.
    """
    if len(sys.argv) > 1:
        # Arguments provided - use CLI mode
        sys.exit(main_cli.main())
    else:
        # No arguments - use interactive mode
        sys.exit(main_interactive.main())


if __name__ == "__main__":
    main()