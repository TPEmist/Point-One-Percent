import os
import uuid
from dotenv import load_dotenv
from aegis.providers.base import VirtualCardProvider
from aegis.core.models import PaymentIntent, GuardrailPolicy, VirtualSeal

class LocalVaultProvider(VirtualCardProvider):
    def __init__(self):
        load_dotenv()
        self.card_number = os.getenv("AEGIS_BYOC_NUMBER")
        self.exp_month = os.getenv("AEGIS_BYOC_EXP_MONTH")
        self.exp_year = os.getenv("AEGIS_BYOC_EXP_YEAR")
        self.cvv = os.getenv("AEGIS_BYOC_CVV")

        # Billing fields are optional — empty string means "not configured"
        self._billing_first_name = os.getenv("AEGIS_BILLING_FIRST_NAME", "").strip()
        self._billing_last_name  = os.getenv("AEGIS_BILLING_LAST_NAME", "").strip()
        self._billing_street     = os.getenv("AEGIS_BILLING_STREET", "").strip()
        self._billing_zip        = os.getenv("AEGIS_BILLING_ZIP", "").strip()
        self._billing_email      = os.getenv("AEGIS_BILLING_EMAIL", "").strip()

        if not all([self.card_number, self.exp_month, self.exp_year, self.cvv]):
            raise ValueError("Missing BYOC environment variables. Please check AEGIS_BYOC_NUMBER, AEGIS_BYOC_EXP_MONTH, AEGIS_BYOC_EXP_YEAR, AEGIS_BYOC_CVV in .env.")

    @property
    def billing_info(self) -> dict:
        """Return billing details as a dict; empty-string values mean not configured."""
        return {
            "first_name": self._billing_first_name,
            "last_name":  self._billing_last_name,
            "street":     self._billing_street,
            "zip":        self._billing_zip,
            "email":      self._billing_email,
        }

    async def issue_card(self, intent: PaymentIntent, policy: GuardrailPolicy) -> VirtualSeal:
        if intent.requested_amount > policy.max_amount_per_tx:
            return VirtualSeal(
                seal_id=str(uuid.uuid4()),
                authorized_amount=0.0,
                status="Rejected",
                rejection_reason="Amount exceeds policy limit"
            )

        return VirtualSeal(
            seal_id=str(uuid.uuid4()),
            card_number=self.card_number,
            cvv=self.cvv,
            expiration_date=f"{self.exp_month}/{self.exp_year}",
            authorized_amount=intent.requested_amount,
            status="Issued"
        )
