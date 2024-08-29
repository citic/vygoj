#!/bin/bash

curl http://localhost:2358/submissions -X POST -d '{ "source_code": "#include <stdio.h>\n\nint main(void) {\n  printf(\"hi!\n\");\n  return 0;\n}", "language_id": 4, "stdin": "world" }' -H 'Content-Type: application/json' -v
