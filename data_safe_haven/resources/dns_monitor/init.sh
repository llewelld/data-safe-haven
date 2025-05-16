#!/bin/bash

export AZURE_CLI_DISABLE_CONNECTION_VERIFICATION=anycontent

echo "Signing in with Azure CLI..."

az login --identity

if [[ $? -ne 0 ]] ; then
    echo "Could not sign in with Azure CLI with managed identity."
    exit 1
fi

echo "Finding container group IP address..."
private_ip=$(az container show --name $CONTAINER_GROUP_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID --query 'ipAddress.ip' -o tsv)
if [[ $? -ne 0 ]] ; then
    echo "Could not find private IP for container group $CONTAINER_GROUP_NAME."
    exit 1
fi
echo "Private IP for container group $CONTAINER_GROUP_NAME: $private_ip"

echo "Deleting previous DNS record..."
az network private-dns record-set a delete --name $RECORD_NAME --zone-name $PRIVATE_ZONE_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID --yes
if [[ $? -ne 0 ]] ; then
    echo "Could not delete DNS record $RECORD_NAME in private zone $PRIVATE_ZONE_NAME."
    exit 1
fi
echo "Record $RECORD_NAME deleted in private zone $PRIVATE_ZONE_NAME"

echo "Creating DNS record ..."
az network private-dns record-set a create --name $RECORD_NAME --zone-name $PRIVATE_ZONE_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID
if [[ $? -ne 0 ]] ; then
    echo "Could not create new DNS record $RECORD_NAME in private zone $PRIVATE_ZONE_NAME."
    exit 1
fi
echo "New record $RECORD_NAME created in private zone $PRIVATE_ZONE_NAME"

az network private-dns record-set a add-record --record-set-name $RECORD_NAME --zone-name $PRIVATE_ZONE_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID --ipv4-address $private_ip
if [[ $? -ne 0 ]] ; then
    echo "Could not add new DNS record $RECORD_NAME in private zone $PRIVATE_ZONE_NAME for IP $private_ip."
    exit 1
fi
echo "DNS record $RECORD_NAME added in private zone $PRIVATE_ZONE_NAME for IP $private_ip."