import os
import sys

if __name__ == "__main__":
    os.execvp(
        sys.executable,
        [sys.executable, "-m", "src.pipelines.harvest", *sys.argv[1:]],
    )
