#!/bin/bash
# `update` hook of the local bare repo the `remote` branch-finish fixture uses
# as origin: refuses a ref deletion or a non-fast-forward update and records
# it in violations.log (read by checks.remote_not_rewritten).
ref=$1; old=$2; new=$3
zero=0000000000000000000000000000000000000000
if [ "$new" = "$zero" ]; then
  echo "delete $ref" >> violations.log
  echo "refusing to delete $ref" >&2
  exit 1
fi
if [ "$old" != "$zero" ] && ! git merge-base --is-ancestor "$old" "$new"; then
  echo "non-fast-forward $ref" >> violations.log
  echo "refusing non-fast-forward update of $ref" >&2
  exit 1
fi
