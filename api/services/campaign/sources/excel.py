import hashlib
from io import BytesIO
from typing import List, Optional

import httpx
import openpyxl
from loguru import logger

from api.db import db_client
from api.services.campaign.source_sync import (
    CampaignSourceSyncService,
    ValidationError,
    ValidationResult,
)
from api.services.storage import storage_fs


class ExcelSyncService(CampaignSourceSyncService):
    """Implementation for Excel (.xlsx/.xls) file synchronization"""

    async def _fetch_excel_data(self, file_key: str) -> List[List[str]]:
        """Download and parse Excel file from storage. Returns all rows including header."""
        signed_url = await storage_fs.aget_signed_url(
            file_key, expiration=3600, use_internal_endpoint=True
        )

        if not signed_url:
            raise ValueError(f"Failed to access Excel file: {file_key}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(signed_url)
                response.raise_for_status()
                excel_bytes = response.content
            except httpx.HTTPError as e:
                logger.error(f"Failed to download Excel file: {e} for url: {signed_url}")
                raise ValueError(f"Failed to download Excel file from storage: {str(e)}")

        return self._parse_excel(excel_bytes)

    async def validate_source(
        self, source_id: str, organization_id: Optional[int] = None
    ) -> ValidationResult:
        """Validate an Excel source file for campaign creation."""
        try:
            excel_data = await self._fetch_excel_data(source_id)
        except ValueError as e:
            return ValidationResult(
                is_valid=False,
                error=ValidationError(message=str(e)),
            )

        if not excel_data or len(excel_data) < 2:
            return ValidationResult(
                is_valid=False,
                error=ValidationError(
                    message="Excel file must have a header row and at least one data row"
                ),
            )

        headers = excel_data[0]
        data_rows = excel_data[1:]

        return self.validate_source_data(headers, data_rows)

    async def sync_source_data(self, campaign_id: int) -> int:
        """
        Fetches data from Excel file in S3/MinIO and creates queued_runs
        """
        # Get campaign
        campaign = await db_client.get_campaign_by_id(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        file_key = campaign.source_id
        excel_data = await self._fetch_excel_data(file_key)

        if not excel_data or len(excel_data) < 2:
            logger.warning(f"No data found in Excel for campaign {campaign_id}")
            return 0

        headers = self.normalize_headers(excel_data[0])
        rows = excel_data[1:]

        # Create hash of file_key for consistent source_uuid prefix
        file_hash = hashlib.md5(file_key.encode()).hexdigest()[:8]

        # Convert to queued_runs
        queued_runs = []
        for idx, row_values in enumerate(rows, 1):
            # Pad row to match headers length
            padded_row = row_values + [""] * (len(headers) - len(row_values))

            # Create context variables dict
            context_vars = dict(zip(headers, padded_row))

            # Skip if no phone number
            if not context_vars.get("phone_number"):
                logger.debug(f"Skipping row {idx}: no phone_number")
                continue

            # Generate unique source UUID: excel_{hash(source_id)}_row_{idx}
            source_uuid = f"excel_{file_hash}_row_{idx}"

            queued_runs.append(
                {
                    "campaign_id": campaign_id,
                    "source_uuid": source_uuid,
                    "context_variables": context_vars,
                    "state": "queued",
                }
            )

        # Bulk insert
        if queued_runs:
            await db_client.bulk_create_queued_runs(queued_runs)
            logger.info(
                f"Created {len(queued_runs)} queued runs for campaign {campaign_id}"
            )

        # Update campaign total_rows
        await db_client.update_campaign(
            campaign_id=campaign_id,
            total_rows=len(queued_runs),
            source_sync_status="completed",
        )

        return len(queued_runs)

    def _parse_excel(self, excel_bytes: bytes) -> List[List[str]]:
        """Parse Excel content into rows"""
        try:
            wb = openpyxl.load_workbook(filename=BytesIO(excel_bytes), data_only=True, read_only=True)
            sheet = wb.active
            rows = []
            for r in sheet.iter_rows(values_only=True):
                # Convert none values to empty strings and convert all values to strings
                row_vals = [str(val) if val is not None else "" for val in r]
                # Only add row if it is not completely empty
                if any(val.strip() for val in row_vals):
                    rows.append(row_vals)
            return rows
        except Exception as e:
            logger.error(f"Failed to parse Excel: {e}")
            raise ValueError(f"Invalid Excel format: {str(e)}")
