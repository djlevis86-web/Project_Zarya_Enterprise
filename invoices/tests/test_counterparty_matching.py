from django.test import TestCase

from invoices.counterparty_service import find_counterparty_by_name
from invoices.models import Counterparty


class CounterpartyMatchingTests(TestCase):
    def test_matches_counterparty_when_legal_form_word_order_differs(self):
        counterparty = Counterparty.objects.create(
            name="БЕЛЫЙ КЛЕВЕР ООО",
            inn="5321188917",
            kpp="532101001",
            source=Counterparty.SOURCE_1C,
            is_active=True,
        )

        found = find_counterparty_by_name(
            "ООО БЕЛЫЙ КЛЕВЕР"
        )

        self.assertEqual(
            found,
            counterparty,
        )

    pass
