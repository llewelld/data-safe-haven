#!/bin/bash

export AZURE_CLI_DISABLE_CONNECTION_VERIFICATION=anycontent

echo "Signing in with Azure CLI..."

az login --identity

if [[ $? -ne 0 ]] ; then
    echo "Could not sign in with Azure CLI."
    exit 1
fi

echo "Finding container group IP address..."