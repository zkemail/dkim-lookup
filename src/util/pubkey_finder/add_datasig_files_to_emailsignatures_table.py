import asyncio
import base64
import hashlib
import logging
import argparse
from common import Dsp, MsgInfo, load_signed_data
from prisma import Prisma
from tqdm import tqdm


async def add_messages_to_db(signed_messages: dict[Dsp, list[MsgInfo]], prisma: Prisma):
	msg_list = list(signed_messages.items())
	max_msgs_per_dsp = 10
	for _dsp, msg_infos in tqdm(msg_list):
		for msg_info in msg_infos[:max_msgs_per_dsp]:
			msg_hash = hashlib.sha256(msg_info.signedData).hexdigest()
			msg_sig = base64.b64encode(msg_info.signature).decode('utf-8')
			emailsig = await prisma.emailsignature.find_first(where={'headerHash': msg_hash, 'dkimSignature': msg_sig})
			if not emailsig:
				res = await prisma.emailsignature.create(data={
				    'domain': _dsp.domain,
				    'selector': _dsp.selector,
				    'headerHash': msg_hash,
				    'dkimSignature': msg_sig,
				    'signingAlgorithm': 'rsa-sha256',
				})
				logging.info(f'created emailsig {res}')
			else:
				logging.info(f'email signature already exists')


async def main():
	parser = argparse.ArgumentParser(allow_abbrev=False)
	parser.add_argument('datasig_files', type=str, nargs='+')
	args = parser.parse_args()
	datasig_files: list[str] = args.datasig_files
	prisma = Prisma()
	await prisma.connect()
	signed_data = load_signed_data(datasig_files)
	await add_messages_to_db(signed_data, prisma)


if __name__ == '__main__':
	asyncio.run(main())
