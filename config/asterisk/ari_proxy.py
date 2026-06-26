import socket
import threading
import select
import urllib.parse
import sys
import os

LISTEN_PORT = 8088
ASTERISK_HOST = 'asterisk'
ASTERISK_PORT = 8088

# Read settings from environment variables passed by docker-compose
VOBIZ_DOMAIN = os.environ.get('VOBIZ_DOMAIN', '455bdb01.sip.vobiz.ai')
DEFAULT_CALLERID = os.environ.get('VOBIZ_CALLERID_NUM', '+918065481144')

def sanitize_endpoint(endpoint_str):
    try:
        decoded = urllib.parse.unquote(endpoint_str)
        if '/' in decoded:
            tech, resource = decoded.split('/', 1)
            tech = tech.strip()
            
            if tech.upper() in ['LOCAL', 'PJSIP']:
                trunk_name = "vobiz-trunk"
                domain = VOBIZ_DOMAIN
                context = "default"
                
                # Check if it has a second slash representing a trunk name
                if '/' in resource:
                    trunk_part, sip_part = resource.split('/', 1)
                    trunk_name = trunk_part.strip()
                    resource = sip_part
                
                # Check if it has @ representing a domain or context
                if '@' in resource:
                    number_part, domain_or_context = resource.split('@', 1)
                    if tech.upper() == 'LOCAL':
                        context = domain_or_context.strip()
                    else:
                        domain = domain_or_context.strip()
                else:
                    number_part = resource
                
                if number_part.lower().startswith('sip:'):
                    number_part = number_part[4:]
                
                has_plus = number_part.strip().startswith('+') or number_part.startswith(' ')
                digits_only = ''.join(c for c in number_part if c.isdigit())
                
                if len(digits_only) >= 5:
                    # Smart E.164 Normalization
                    if len(digits_only) == 10:
                        cleaned_number = f"+91{digits_only}"
                    elif len(digits_only) == 12 and digits_only.startswith('91'):
                        cleaned_number = f"+{digits_only}"
                    else:
                        prefix = "+" if has_plus else ""
                        cleaned_number = f"{prefix}{digits_only}"
                    
                    if tech.upper() == 'LOCAL':
                        new_endpoint = f"Local/{cleaned_number}@{context}"
                    else:
                        new_endpoint = f"PJSIP/{trunk_name}/sip:{cleaned_number}@{domain}"
                        
                    print(f"[ARI Proxy] Normalized & Rewrote endpoint '{endpoint_str}' -> '{new_endpoint}'", flush=True)
                    return new_endpoint
    except Exception as e:
        print(f"[ARI Proxy] Error parsing endpoint '{endpoint_str}': {e}", flush=True)
    return endpoint_str

def sanitize_callerid(callerid_str):
    if not callerid_str:
        return DEFAULT_CALLERID
    # Verify the callerId is a valid phone number (at least 10 digits)
    digits_only = ''.join(c for c in callerid_str if c.isdigit())
    if len(digits_only) < 10:
        return DEFAULT_CALLERID
    return callerid_str

def trigger_ami_reload():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect((ASTERISK_HOST, 5038))
        
        # Read Asterisk Call Manager banner
        s.recv(1024)
        
        # Login
        login_cmd = "Action: Login\r\nUsername: admin\r\nSecret: admin_pass\r\n\r\n"
        s.sendall(login_cmd.encode('utf-8'))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = s.recv(1024)
            if not chunk:
                break
            response += chunk
            
        # PJSIP Reload
        pjsip_cmd = "Action: Command\r\nCommand: pjsip reload\r\n\r\n"
        s.sendall(pjsip_cmd.encode('utf-8'))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = s.recv(1024)
            if not chunk:
                break
            response += chunk
            
        # Dialplan Reload
        dialplan_cmd = "Action: Command\r\nCommand: dialplan reload\r\n\r\n"
        s.sendall(dialplan_cmd.encode('utf-8'))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = s.recv(1024)
            if not chunk:
                break
            response += chunk
            
        # Logoff
        s.sendall(b"Action: Logoff\r\n\r\n")
        s.close()
        print("[ARI Proxy] Asterisk configurations reloaded via AMI successfully.", flush=True)
        return True
    except Exception as e:
        print(f"[ARI Proxy] Failed to reload Asterisk via AMI: {e}", flush=True)
        return False

def handle_client(client_socket):
    try:
        data = client_socket.recv(65536)
        if not data:
            client_socket.close()
            return
    except Exception:
        client_socket.close()
        return

    try:
        parts = data.split(b'\r\n\r\n', 1)
        header_bytes = parts[0]
        body_bytes = parts[1] if len(parts) > 1 else b''
        
        header_text = header_bytes.decode('utf-8', errors='ignore')
        lines = header_text.split('\r\n')
        request_line = lines[0]
        request_parts = request_line.split(' ')
        
        if len(request_parts) >= 2 and request_parts[0] == 'POST' and request_parts[1] == '/reload':
            success = trigger_ami_reload()
            if success:
                response = b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            else:
                response = b"HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            client_socket.sendall(response)
            client_socket.close()
            return

        if len(request_parts) >= 2 and request_parts[0] == 'POST' and ('/channels' in request_parts[1] or '/ari/channels' in request_parts[1]):
            method, uri, version = request_parts[0], request_parts[1], request_parts[2]
            
            # 1. Sanitize inside URI query parameters
            url_parsed = urllib.parse.urlparse(uri)
            query_params = urllib.parse.parse_qs(url_parsed.query, keep_blank_values=True)
            
            modified = False
            if 'endpoint' in query_params:
                original_endpoint = query_params['endpoint'][0]
                cleaned_endpoint = sanitize_endpoint(original_endpoint)
                if original_endpoint != cleaned_endpoint:
                    query_params['endpoint'] = [cleaned_endpoint]
                    modified = True
            
            # Sanitize & enforce callerId in query parameters
            if 'callerId' in query_params:
                original_cid = query_params['callerId'][0]
                cleaned_cid = sanitize_callerid(original_cid)
                if original_cid != cleaned_cid:
                    query_params['callerId'] = [cleaned_cid]
                    modified = True
            else:
                query_params['callerId'] = [DEFAULT_CALLERID]
                modified = True
            
            if modified:
                new_query = urllib.parse.urlencode(query_params, doseq=True, quote_via=urllib.parse.quote)
                new_uri = url_parsed.path
                if new_query:
                    new_uri += '?' + new_query
                lines[0] = f"{method} {new_uri} {version}"
                header_text = '\r\n'.join(lines)
                header_bytes = header_text.encode('utf-8')
            
            # 2. Sanitize inside POST body
            content_type = ""
            for line in lines:
                if line.lower().startswith("content-type:"):
                    content_type = line.split(":", 1)[1].strip().lower()
                    break
            
            if body_bytes:
                body_modified = False
                if "application/json" in content_type:
                    import json
                    try:
                        body_json = json.loads(body_bytes.decode('utf-8'))
                        if isinstance(body_json, dict):
                            if 'endpoint' in body_json:
                                original_endpoint = body_json['endpoint']
                                cleaned_endpoint = sanitize_endpoint(original_endpoint)
                                if original_endpoint != cleaned_endpoint:
                                    body_json['endpoint'] = cleaned_endpoint
                                    body_modified = True
                            
                            if 'callerId' in body_json:
                                original_cid = body_json['callerId']
                                cleaned_cid = sanitize_callerid(original_cid)
                                if original_cid != cleaned_cid:
                                    body_json['callerId'] = cleaned_cid
                                    body_modified = True
                            else:
                                body_json['callerId'] = DEFAULT_CALLERID
                                body_modified = True
                                
                            if body_modified:
                                body_bytes = json.dumps(body_json).encode('utf-8')
                    except Exception as json_err:
                        print(f"[ARI Proxy] JSON parse error: {json_err}", flush=True)
                elif "application/x-www-form-urlencoded" in content_type:
                    try:
                        body_params = urllib.parse.parse_qs(body_bytes.decode('utf-8'), keep_blank_values=True)
                        if 'endpoint' in body_params:
                            original_endpoint = body_params['endpoint'][0]
                            cleaned_endpoint = sanitize_endpoint(original_endpoint)
                            if original_endpoint != cleaned_endpoint:
                                body_params['endpoint'] = [cleaned_endpoint]
                                body_modified = True
                        
                        if 'callerId' in body_params:
                            original_cid = body_params['callerId'][0]
                            cleaned_cid = sanitize_callerid(original_cid)
                            if original_cid != cleaned_cid:
                                body_params['callerId'] = [cleaned_cid]
                                body_modified = True
                        else:
                            body_params['callerId'] = [DEFAULT_CALLERID]
                            body_modified = True
                            
                        if body_modified:
                            body_bytes = urllib.parse.urlencode(body_params, doseq=True, quote_via=urllib.parse.quote).encode('utf-8')
                    except Exception as form_err:
                        print(f"[ARI Proxy] Form urlencode parse error: {form_err}", flush=True)
                
                if body_modified:
                    new_len = len(body_bytes)
                    for i, line in enumerate(lines):
                        if line.lower().startswith("content-length:"):
                            lines[i] = f"Content-Length: {new_len}"
                            break
                    header_text = '\r\n'.join(lines)
                    header_bytes = header_text.encode('utf-8')
            
            data = header_bytes + b'\r\n\r\n' + body_bytes

    except Exception as e:
        print(f"[ARI Proxy] Non-fatal request parsing error: {e}", flush=True)

    # Forward to Asterisk
    asterisk_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        asterisk_socket.connect((ASTERISK_HOST, ASTERISK_PORT))
    except Exception as e:
        print(f"[ARI Proxy] Failed to connect to Asterisk backend: {e}", flush=True)
        client_socket.close()
        return

    try:
        asterisk_socket.sendall(data)
    except Exception as e:
        print(f"[ARI Proxy] Failed to forward initial request: {e}", flush=True)
        client_socket.close()
        asterisk_socket.close()
        return

    # Pipe bidirectional tunnel (works perfectly for both HTTP and WebSockets)
    sockets = [client_socket, asterisk_socket]
    try:
        while True:
            readable, _, exceptional = select.select(sockets, [], sockets, 60)
            if exceptional:
                break
            for sock in readable:
                other_sock = asterisk_socket if sock is client_socket else client_socket
                chunk = sock.recv(8192)
                if not chunk:
                    raise Exception("Connection closed")
                other_sock.sendall(chunk)
    except Exception:
        pass
    finally:
        client_socket.close()
        asterisk_socket.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', LISTEN_PORT))
    server.listen(128)
    print(f"[ARI Proxy] Sanitizer Proxy listening on port {LISTEN_PORT}...", flush=True)
    
    while True:
        try:
            server_sock, _ = server.accept()
            t = threading.Thread(target=handle_client, args=(server_sock,))
            t.daemon = True
            t.start()
        except KeyboardInterrupt:
            break
        except Exception:
            pass

if __name__ == '__main__':
    main()
