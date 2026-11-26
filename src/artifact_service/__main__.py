import argparse
import uvicorn
from .config import load_config
from .main import create_app

def main():
    parser=argparse.ArgumentParser(description='Read-only remote artifact browser')
    parser.add_argument('--config',default='config/config.json')
    args=parser.parse_args(); cfg=load_config(args.config)
    uvicorn.run(create_app(cfg),host=cfg.host,port=cfg.port,access_log=False)

if __name__=='__main__': main()
