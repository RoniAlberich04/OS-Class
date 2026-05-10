# This script creates Linux student accounts from a CSV file.
# CSV format:
# student_id,last_name,first_name
#
# Example:
# sudo ./create_students.sh 2023_fall.csv

set -euo pipefail

DEFAULT_PASSWORD="ChangeMe123!"
GROUP_NAME="students"

if [ "$#" -ne 1 ]; then
    echo "Usage: sudo ./create_students.sh year_semester.csv"
    exit 1
fi

INPUT_FILE="$1"

if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: CSV file '$INPUT_FILE' was not found."
    exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "Error: Please run this script with sudo."
    exit 1
fi

# The assignment says the students group should be created before running.
if ! getent group "$GROUP_NAME" > /dev/null; then
    echo "Error: Group '$GROUP_NAME' does not exist."
    echo "Create it first with: sudo groupadd students"
    exit 1
fi

BASENAME="${INPUT_FILE%.csv}"
OUTPUT_FILE="${BASENAME}_users.csv"

echo "student_id,username" > "$OUTPUT_FILE"

# Skip the first line because it is the CSV header.
tail -n +2 "$INPUT_FILE" | while IFS=',' read -r student_id last_name first_name; do
    # Remove spaces that may appear around CSV values.
    student_id="$(echo "$student_id" | xargs)"
    last_name="$(echo "$last_name" | xargs)"
    first_name="$(echo "$first_name" | xargs)"

    if [ -z "$student_id" ] || [ -z "$last_name" ] || [ -z "$first_name" ]; then
        echo "Skipping invalid row: $student_id,$last_name,$first_name"
        continue
    fi

    # Create username from first initial, last name, and student id.
    # Example: John Doe with id 1234 becomes jdoe1234.
    first_initial="$(echo "${first_name:0:1}" | tr '[:upper:]' '[:lower:]')"
    clean_last_name="$(echo "$last_name" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9')"
    clean_student_id="$(echo "$student_id" | tr -cd 'a-zA-Z0-9')"
    username="${first_initial}${clean_last_name}${clean_student_id}"

    if id "$username" > /dev/null 2>&1; then
        echo "User '$username' already exists. Skipping creation."
    else
        # Create the Linux user with a home folder and add them to students group.
        useradd -m -g "$GROUP_NAME" -s /bin/bash "$username"

        # Set a default password and force the student to change it at first login.
        echo "$username:$DEFAULT_PASSWORD" | chpasswd
        chage -d 0 "$username"

        # Create required folders inside the student's home directory.
        mkdir -p "/home/$username/documents"
        mkdir -p "/home/$username/code"

        # Create a simple policy file for the student.
        cat > "/home/$username/POLICY.md" << POLICY
# Lab Server Policy

- Use this account only for programming course work.
- Do not share your password with anyone.
- Change your password when you first log in.
- Store documents in the documents folder.
- Store programming files in the code folder.
- Do not delete or change other users' files.
POLICY

        # Give the student read, write, and execute rights on their own home folder.
        chown -R "$username:$GROUP_NAME" "/home/$username"
        chmod 700 "/home/$username"

        echo "Created user '$username'."
    fi

    echo "$student_id,$username" >> "$OUTPUT_FILE"
done

echo "Done. Generated usernames were saved in '$OUTPUT_FILE'."
