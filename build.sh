#!/bin/bash
docker build -t automate-aurora-new-version-checking-build .
docker run --rm -v ${PWD}/bin:/vol automate-aurora-new-version-checking-build
