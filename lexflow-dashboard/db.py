import logging
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def get_table(table_name: str, region: str = "us-east-1"):
    dynamodb = boto3.resource("dynamodb", region_name=region)
    return dynamodb.Table(table_name)


def put_item(table_name: str, item: dict, region: str = "us-east-1") -> None:
    """Write a full intake record to DynamoDB."""
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
    """Scan and return all records."""
    table = get_table(table_name, region)
    try:
        response = table.scan()
        items = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))

        logger.info("DynamoDB scan returned %d records", len(items))
        return items
    except ClientError as e:
        logger.error("DynamoDB scan failed | error=%s", e.response["Error"]["Message"])
        raise


def get_item(table_name: str, intake_id: str, region: str = "us-east-1") -> dict | None:
    """
    Fetch a single intake record by intake_id.
    Returns None if not found.
    """
    table = get_table(table_name, region)
    try:
        response = table.get_item(Key={"intake_id": intake_id})
        item = response.get("Item")
        if item:
            logger.info("DynamoDB get success | intake_id=%s", intake_id)
        else:
            logger.warning("DynamoDB get — item not found | intake_id=%s", intake_id)
        return item
    except ClientError as e:
        logger.error(
            "DynamoDB get failed | intake_id=%s | error=%s",
            intake_id,
            e.response["Error"]["Message"],
        )
        raise


def update_status(
    table_name: str,
    intake_id: str,
    new_status: str,
    note: str = "",
    region: str = "us-east-1"
) -> None:
    """
    Update the status of an intake record.
    Also logs who changed it and when.
    """
    table = get_table(table_name, region)
    updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    try:
        table.update_item(
            Key={"intake_id": intake_id},
            UpdateExpression=(
                "SET #s = :status, "
                "updated_at = :updated_at, "
                "attorney_note = :note"
            ),
            ExpressionAttributeNames={
                "#s": "status"  # 'status' is a reserved word in DynamoDB
            },
            ExpressionAttributeValues={
                ":status": new_status,
                ":updated_at": updated_at,
                ":note": note,
            },
            ConditionExpression="attribute_exists(intake_id)",
        )
        logger.info(
            "Status updated | intake_id=%s | status=%s",
            intake_id,
            new_status
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ConditionalCheckFailedException":
            logger.error("Status update failed — intake_id not found | %s", intake_id)
            raise ValueError(f"Case {intake_id} not found in database.")
        logger.error(
            "Status update failed | intake_id=%s | error=%s",
            intake_id,
            e.response["Error"]["Message"],
        )
        raise