"""Run an unchanged stdin/stdout program inside the parent-created OS sandbox."""
import json
import os
import resource
import runpy
import sys


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (131072, 131072))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    sys.dont_write_bytecode = True
    sys.path.insert(0, os.getcwd())
    covered = sys.argv[1] == 'coverage'
    # No expected answer, test suite, metadata or credentials enter this worker.
    from __repair_coverage import Coverage
    tracer = Coverage(['main.py'])
    sys.argv = ['main.py']
    if covered:
        sys.settrace(tracer)
    try:
        runpy.run_path(os.path.abspath('main.py'), run_name='__main__')
    finally:
        intact = covered and sys.gettrace() is tracer
        sys.settrace(None)
        if covered:
            data = tracer.export(intact)
            data['version'] = 'stdin-main-line-coverage-v1'
            with open(os.path.join(os.environ['TMPDIR'], 'coverage.json'), 'w') as handle:
                json.dump(data, handle, allow_nan=False)


if __name__ == '__main__':
    main()
