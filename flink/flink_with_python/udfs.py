from datetime import datetime
import re
from pyflink.table.udf import udf

@udf(result_type='MAP<STRING, STRING>')
def parse_log(line: str):
    try:
        pattern = re.compile(
            r'(?P<ip>\S+) - - \[(?P<datetime>[^\]]+)\] time:(?P<response_time>[\d.]+) s "(?P<method>[A-Z]+) (?P<url>\S+) (?P<protocol>[^"]+)" (?P<status>\d{3}) (?P<size>\d+) "[^"]*" "(?P<user_agent>[^"]+)"'
        )
        match = pattern.match(line)
        if match:
            gd = match.groupdict()
            dt = datetime.strptime(gd['datetime'], '%d/%b/%Y:%H:%M:%S %z')
            url = gd['url']

            if '?' in url:
                path, param = url.split('?', 1)
            else:
                path, param = url, '-'

            return {
                'ip': gd['ip'],
                'time': dt.strftime('%Y-%m-%d %H:%M:%S'),
                'method': gd['method'],
                'url': path,
                'param': param,
                'protocol': gd['protocol'],
                'responseTime': gd['response_time'],
                'responseCode': gd['status'],
                'responseByte': gd['size'],
                'user-agent': gd['user_agent']
            }
        else:
            return {}
    except Exception as e:
        return {}

def register_udfs(t_env):
    """Register all UDFs with the given table environment."""
    t_env.create_temporary_system_function("parse_log", parse_log)

