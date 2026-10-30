"""Same methods as SyntheticAdapter; plugs into a Paytm sandbox once one exists."""


class PaytmAdapter:
    def __getattr__(self, name: str):
        def missing(*args, **kwargs):
            raise NotImplementedError(f"PaytmAdapter.{name}: no Paytm sandbox yet. Use SyntheticAdapter.")
        return missing
