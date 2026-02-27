import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def get_table(table_name: str, region: str = "us-east-1"):
    dynamodb = boto3.resource("dynamodb", region_name=region)
    return dynamodb.Table(table_name)


def put_item(table_name: str, item: dict, region: str = "us-east-1") -> None:
    """
    Write a full intake record to DynamoDB.
    Raises on failure — caller decides how to handle.
    """
    table = get_table(table_name, region)
    try:
        table.put_item(Item=item)
        logger.info("DynamoDB write success | intake_id=%s", item.get("intake_id"))
    except ClientError as e:
        logger.error(
            "DynamoDB write failed | intake_id=%s | error=%s",
            item.get("intake_id"),
            e.response["Error"]["Message"],
        )
        raise


def scan_all(table_name: str, region: str = "us-east-1") -> list[dict]:
    """
    Scan and return all records. Fine at hackathon scale.
    """
    table = get_table(table_name, region)
    try:
        response = table.scan()
        items = response.get("Items", [])

        # Handle DynamoDB pagination (unlikely at hackathon scale, but correct)
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))

        logger.info("DynamoDB scan returned %d records", len(items))
        return items
    except ClientError as e:
        logger.error("DynamoDB scan failed | error=%s", e.response["Error"]["Message"])
        raise
def get_by_token(table_name: str, portal_token: str, region: str = "us-east-1") -> dict | None:
    """
    Look up an intake record by portal_token using a DynamoDB scan with filter.
    Returns the record dict or None if not found.
    """
    table = get_table(table_name, region)
    response = table.scan(
        FilterExpression="portal_token = :token",
        ExpressionAttributeValues={":token": portal_token},
        Limit=1,
    )
    items = response.get("Items", [])
    return items[0] if items else None