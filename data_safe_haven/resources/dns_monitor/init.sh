#!/bin/bash

echo "Signing in with Azure CLI..."
# For authenticating with Azure CLI, it's necessary to allow traffic to the service tag AzureActiveDirectory.
az login --identity --client-id $CLIENT_ID

if [[ $? -ne 0 ]] ; then
    echo "Could not sign in with Azure CLI with managed identity."
    exit 1
fi

IFS=',' read -ra RECORD_NAME_CONTAINER_GROUP <<< "$RECORD_NAMES_CONTAINER_GROUPS"
for RECORD_NAME_CONTAINER_GROUP in "${RECORD_NAME_CONTAINER_GROUP[@]}"; do
    as_array=($RECORD_NAME_CONTAINER_GROUP)
    RECORD_NAME=${as_array[0]}
    CONTAINER_GROUP_NAME=${as_array[1]}

    # The IP resolution and DNS update are done through the Azure Resource Manager REST API. Hence, we need to allow traffic to the service tag AzureResourceManager.
    echo "Finding container group IP address..."
    private_ip=$(az container show --name $CONTAINER_GROUP_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID --query 'ipAddress.ip' -o tsv)
    if [[ $? -ne 0 ]] ; then
        echo "Could not find private IP for container group $CONTAINER_GROUP_NAME."
        exit 1
    fi
    echo "Private IP for container group $CONTAINER_GROUP_NAME: $private_ip"

    echo "Updating DNS record..."
    az network private-dns record-set a update --name $RECORD_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID --zone-name $PRIVATE_ZONE_NAME --set aRecords[0].ipv4Address=$private_ip
    if [[ $? -ne 0 ]] ; then
        echo "Could not update DNS record $RECORD_NAME in private zone $PRIVATE_ZONE_NAME."
        exit 1
    fi
    echo "Record $RECORD_NAME updated in private zone $PRIVATE_ZONE_NAME"
done