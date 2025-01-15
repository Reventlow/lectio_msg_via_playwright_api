import sys
from os import getenv
from decouple import config
from icecream import ic


# function that first trys to get environment variables from .env file, if not found it will get them from the os
def get_env_variable(var_name: str, default_value: str = None) -> str:
    try:
        return config(var_name)
    except KeyError:
        if default_value is not None:
            return default_value
        raise
        ic(f"KeyError : Environment variable {var_name} not found in .env file. Trying to get it from the os")
        try:
            ic(f"Trying to get environment variable {var_name} from the os")
            return getenv(var_name)
        except OSError:
            error_msg = f"OSError : Environment variable {var_name} not found in .env file or in the os"
            ic(error_msg)
            sys.exit(1)
        except Exception as e:
            error_msg = f"Exception: Error in getting environment variable {var_name}. Exception: {e}"
            ic(error_msg)
            sys.exit(1)


def main():
    pass


if __name__ == '__main__':
    main()
