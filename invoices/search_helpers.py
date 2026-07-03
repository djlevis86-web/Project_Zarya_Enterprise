from django.db.models import Q


def get_search_variants(search_query):

    search_query = (
        search_query or ''
    ).strip()

    if not search_query:
        return []

    raw_variants = [
        search_query,
        search_query.lower(),
        search_query.upper(),
        search_query.title(),
        ' '.join(
            word.capitalize()
            for word in search_query.split()
        ),
    ]

    variants = []

    for variant in raw_variants:

        variant = (
            variant or ''
        ).strip()

        if variant and variant not in variants:
            variants.append(
                variant
            )

    return variants


def build_multi_variant_search_q(search_query, field_names):

    search_q = Q()

    for variant in get_search_variants(
        search_query
    ):

        for field_name in field_names:

            search_q |= Q(
                **{
                    f'{field_name}__icontains': variant,
                }
            )

    return search_q
