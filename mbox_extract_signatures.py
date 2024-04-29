import os
import argparse
import sys
import mailbox
import base64

sys.path.insert(0, "dkimpy")
import dkimpy.dkim as dkim
from dataclasses import dataclass

# https://russell.ballestrini.net/quickstart-to-dkim-sign-email-with-python/

def decode_dkim_header_field(dkimData: str):
    # decode a DKIM-Signature header field such as "v=1; a=rsa-sha256; d=example.net; s=brisbane;"
    # to a dictionary such as {'v': '1', 'a': 'rsa-sha256', 'd': 'example.net', 's': 'brisbane'}
    tagValuePairStrings = list(map(lambda x: x.strip(), dkimData.split(';')))
    res: dict[str, str] = {}
    for s in tagValuePairStrings:
        if not s:
            continue
        key, value = s.split('=', 1)
        key = key.strip()
        value = value.strip()
        res[key] = value
    return res


@dataclass
class MsgInfo:
    signedData: bytes
    signature: bytes


def write_msg_info(msgInfo: MsgInfo, outDir: str, dskey: str, index: int):
    outDirDsp = os.path.join(outDir, dskey)
    outDirDspMsgN = os.path.join(outDirDsp, str(index))
    if not os.path.exists(outDirDspMsgN):
        os.makedirs(outDirDspMsgN)
    with open(os.path.join(outDirDspMsgN, 'data'), 'wb') as f:
        f.write(msgInfo.signedData)
    with open(os.path.join(outDirDspMsgN, 'data.sig'), 'wb') as f:
        f.write(msgInfo.signature)


def main():
    parser = argparse.ArgumentParser(description='extract domains and selectors from the DKIM-Signature header fields in an mbox file and output them in TSV format')
    parser.add_argument('mbox_file')
    parser.add_argument('output_dir')
    parser.add_argument('--skip', type=int, default=0, help='skip the first N messages')
    parser.add_argument('--take', type=int, default=0, help='take the first N messages (0 = all remaining)')
    args = parser.parse_args()
    mbox_file = args.mbox_file
    print(f'processing {mbox_file}', file=sys.stderr)
    outDir = args.output_dir
    if not os.path.exists(outDir):
        os.makedirs(outDir)
    gitignore_path = os.path.join(outDir, '.gitignore')
    with open(gitignore_path, 'w') as f:
        f.write('*\n')
    results: dict[str, list[MsgInfo]] = {}
    message_counter = 0
    print(f'processing {args.mbox_file}', file=sys.stderr)
    mb = mailbox.mbox(args.mbox_file)
    print(f'loaded {args.mbox_file}', file=sys.stderr)
    skip = args.skip
    take = args.take
    for message in mb:
        message_counter += 1
        if message_counter <= skip:
            continue
        if take > 0 and message_counter > skip + take:
            break

        print(f'-----------------------{message_counter}-------------------------', file=sys.stderr)
        dkimSignatureFields = message.get_all('DKIM-Signature')
        if not dkimSignatureFields:
            print('no DKIM-Signature header field found, skipping', file=sys.stderr)
            continue
        for field in dkimSignatureFields:
            tags = decode_dkim_header_field(field)
            domain = tags['d']
            selector = tags['s']
            signAlgo = tags['a']
            if signAlgo != 'rsa-sha256' and signAlgo != 'rsa-sha1':
                print(f'skip signAlgo that is not rsa-sha256 or rsa-sha1: {signAlgo}', file=sys.stderr)
                continue
            bodyHash = tags.get('bh', None)
            if not bodyHash:
                print('body hash not found, skipping', file=sys.stderr)
                continue
            bodyLen = tags.get('l', None)
            if bodyLen:
                print('body length param not supported yet, skipping', file=sys.stderr)
                continue
            signature_tag = tags.get('b', None)
            if not signature_tag:
                print('signature tag not found, skipping', file=sys.stderr)
                continue
            signature_base64 = ''.join(list(map(lambda x: x.strip(), signature_tag.splitlines())))
            signature = base64.b64decode(signature_base64)

            infoOut = {}
            try:
                d = dkim.DKIM(str(message).encode(), debug_content=True)
            except UnicodeEncodeError as e:
                print(f'WARNING: UnicodeEncodeError: {e}', file=sys.stderr)
                continue

            try:
                d.verify(0, infoOut=infoOut)
            except dkim.ValidationError as e:
                print(f'WARNING: ValidationError: {e}', file=sys.stderr)
                continue
            body_hash_mismatch = infoOut.get('body_hash_mismatch', False)
            try:
                signed_data = infoOut['signed_data']
            except KeyError:
                print('signed_data not found', file=sys.stderr)
                print(f'infoOut: {infoOut}', file=sys.stderr)
                sys.exit(1)

            print(f'register message info for {domain} and {selector}', file=sys.stderr)
            dskey = (body_hash_mismatch and "BHM_" or "") + domain + "_" + selector
            msg_info = MsgInfo(signed_data, signature)
            if dskey in results:
                existing_results = results[dskey]
                print(f'store message info for {dskey}', file=sys.stderr)
                if len(existing_results) == 1:
                    write_msg_info(existing_results[0], outDir, dskey, 0)
                write_msg_info(msg_info, outDir, dskey, len(results[dskey]))
            else:
                results[dskey] = []
            results[dskey].append(msg_info)


if __name__ == '__main__':
    main()
