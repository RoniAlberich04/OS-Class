# Linux Student User Management

This project has two Bash scripts for a Linux lab server.

## Files

- `create_students.sh` creates student users from a CSV file.
- `remove_students.sh` archives student home folders and then removes the users.

## Input CSV

The input file must look like this:

```csv
student_id,last_name,first_name
1234,Doe,John
```

For John Doe with id `1234`, the username will be:

```text
jdoe1234
```

## Before Running

On the Linux server, create the students group first:

```bash
sudo groupadd students
```

## Create Users

Run:

```bash
sudo ./create_students.sh 2023_fall.csv
```

The script will:

- create each student user
- add each user to the `students` group
- create `documents` and `code` folders
- create a `POLICY.md` file in the home folder
- set a default password
- force the student to change the password at first login
- save usernames in `2023_fall_users.csv`

## Remove Users

Run:

```bash
sudo ./remove_students.sh 2023_fall_users.csv
```

The script will:

- read the generated users CSV file
- ask for confirmation before deleting users
- create a compressed archive in `archives/2023_fall.tar`
- remove users only if the archive was created successfully
