import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { getServerSession } from "next-auth/next"
import { authOptions } from "@/app/auth";
import { addDomainSelectorPair } from '@/lib/addDomainSelectorPair';

export async function GET(request: NextRequest) {
	const session = await getServerSession(authOptions);

	if (!session || !session.user?.email) {
		return new Response('Unauthorized. Sign in via api/auth/signin', { status: 401 });
	}
	try {
		console.log(`request url: ${request.nextUrl}`);
		let domain = request.nextUrl.searchParams.get('domain');
		if (!domain) {
			throw 'missing domain parameter in query';
		}
		let selector = request.nextUrl.searchParams.get('selector');
		if (!selector) {
			throw 'missing selector parameter in query';
		}
		await addDomainSelectorPair(domain, selector);

		return NextResponse.json(
			{ message: `updated ${domain}, ${selector}` },
			{ status: 200 }
		);
	} catch (error) {
		console.log(`error updating: ${error}`, error);
		return NextResponse.json(
			{ error: `${error}` },
			{ status: 500 }
		);
	}
}