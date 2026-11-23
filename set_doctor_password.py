

from getpass import getpass
from werkzeug.security import generate_password_hash
from database import get_connection

email = input("Enter doctor's registered email: ").strip()
password = getpass("Create doctor's password: ")
confirm = getpass("Confirm password: ")

if not password or password != confirm:
    print("Password empty hai ya match nahi hua.")
    raise SystemExit

connection = get_connection()

if connection is None:
    print("Database connection failed.")
    raise SystemExit

cursor = None

try:
    cursor = connection.cursor()

    cursor.execute(
        "SELECT doctor_id FROM doctors WHERE email = %s",
        (email,)
    )

    doctor = cursor.fetchone()

    if doctor is None:
        print("Doctor email nahi mila.")
    else:
        password_hash = generate_password_hash(password)

        cursor.execute(
            "UPDATE doctors SET password_hash = %s WHERE email = %s",
            (password_hash, email)
        )

        connection.commit()
        print("Doctor password successfully set!")

except Exception:
    connection.rollback()
    print("Password setup failed.")
    raise

finally:
    if cursor:
        cursor.close()
    connection.close()
