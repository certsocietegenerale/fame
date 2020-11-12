import sys
import getpass


def error(msg, code=1, exit=True):
    print(("\n/!\\ {}".format(msg)))

    if exit:
        sys.exit(code)


def user_input(prompt, default=None, choices=[]):
    prompt = "[?] {}".format(prompt)

    if default:
        prompt += " [{}]: ".format(default)
    else:
        prompt += ": "

    while True:
        value = input(prompt).strip()

        if value:
            if choices and value not in choices:
                print(("[!] Invalid choice: {}".format(value)))
                continue

            return value
        elif default:
            return default


def get_new_password():
    password = ""
    while not password:
        password = getpass.getpass("[?] Password: ")
        confirmation = getpass.getpass("[?] Confirm: ")

        if password != confirmation:
            print("Passwords do not match ...")
            password = ""

    return password
