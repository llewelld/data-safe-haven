#!/bin/bash

export AZURE_CLI_DISABLE_CONNECTION_VERIFICATION=anycontent

az login --identity

if [[ $? -ne 0 ]] ; then
    echo "Could not sign in with Azure CLI."
    exit 1
fi
