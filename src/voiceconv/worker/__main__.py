"""Entry point for the inference worker process.

Launch as:  python -m voiceconv.worker --engine <engine_id>

The worker reads length-prefixed JSON from stdin, dispatches model calls,
and writes responses to stdout.  All diagnostic output goes to stderr, which
is inherited from the parent process (WorkerAdapter).
"""

import argparse
import logging
import sys

from voiceconv.worker import host
from voiceconv.worker.engines import REGISTRY


def main() -> None:
    parser = argparse.ArgumentParser(
        description="voiceconv inference worker process",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--engine",
        required=True,
        choices=sorted(REGISTRY),
        help="engine id to serve (e.g. openvoice_v2, freevc, mock)",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="logging level written to stderr",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    host.run(allowed_engine=args.engine)


if __name__ == "__main__":
    main()
