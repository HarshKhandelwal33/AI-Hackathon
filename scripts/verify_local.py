"""Exercise all MCP tools against local SereneDB, without a model API call."""
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from loglens.agent import call_mcp

async def main():
    async with stdio_client(StdioServerParameters(command=sys.executable,args=['-m','loglens.server'])) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            names={t.name for t in (await session.list_tools()).tools}
            async def check(name,args):
                import json
                result=await call_mcp(session,names,name,json.dumps(args))
                assert not result.get('isError') and 'evidence' in result, (name,result)
                print('PASS',name)
                return result['evidence']
            await check('get_corpus_overview',{})
            for dataset, phrase in [('bgl','data TLB error interrupt'),('openstack','qemu-img Could not open')]:
                search=await check('search_logs',{'dataset':dataset,'text':phrase})
                table=search['rows']
                event_id=table['values'][0][table['columns'].index('event_id')]
                await check('get_nearby_events',{'dataset':dataset,'event_id':event_id})
                for group in ['component','team']:
                    await check('summarize_logs',{'dataset':dataset,'group_by':group})
                await check('get_log_trend',{'dataset':dataset,'bucket':'week','text':phrase})
            await check('search_related_logs',{'dataset':'openstack','phrases':['qemu-img','No valid host']})
            await check('investigate_error',{'dataset':'openstack','text':'qemu-img Could not open'})
            empty=await check('investigate_error',{'dataset':'openstack','text':'nonexistent_error_xyz'})
            assert empty['search']['result_count']==0 and 'context' not in empty
            print('All local integration checks passed')
if __name__=='__main__':
    asyncio.run(main())
