import os
from unittest.mock import patch

import app


def test_token_icon_endpoint_download_and_cache(tmp_path):
    # Use a temporary static folder by overriding app.static_folder for the test
    original_static = app.app.static_folder
    try:
        app.app.static_folder = str(tmp_path)
        # Ensure the cache dir is based on app.root_path/static/token_icons
        contract = '0xdeadbeef'
        network = 'arbitrum'

        # Prepare fake png bytes
        fake_png = b'\x89PNG\r\n\x1a\n' + b'FAKEPNGDATA'

        class MockResp:
            status_code = 200
            content = fake_png
            def raise_for_status(self):
                return None

        with patch('app.requests.get', return_value=MockResp()):
            client = app.app.test_client()
            # First request should trigger a download and return the image
            res = client.get(f'/token_icon/{network}/{contract}')
            assert res.status_code == 200
            assert res.data.startswith(b'\x89PNG')

            # The file should now exist in the cache dir
            cache_dir = os.path.join(app.app.root_path, 'static', 'token_icons', network)
            filename = os.path.join(cache_dir, contract.lower().replace('0x', '') + '.png')
            assert os.path.exists(filename)

            # Second request should serve from cache (still 200)
            res2 = client.get(f'/token_icon/{network}/{contract}')
            assert res2.status_code == 200
            assert res2.data.startswith(b'\x89PNG')
    finally:
        app.app.static_folder = original_static
