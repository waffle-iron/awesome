import sys
import pytest
sys.path.append('../www')
from app import *


@pytest.fixture()
def cli(aiohttp_client,loop):
    app = loop.run_until_complete(init(loop))
    return loop.run_until_complete(aiohttp_client(app))


async def test_set_value(cli):
    resp = await cli.post('/api/authenticate', data=json.dumps({'email': "363635454@qq.com", 'passwd': "27922566adf26f7361d17da3cffa68d50155ae55"}))
    assert resp.status == 200
    assert (await resp.json())['name'] == 'Ark'


if __name__ == "__main__":
    pytest.main()
