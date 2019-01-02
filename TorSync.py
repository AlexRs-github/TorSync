import pymysql, subprocess, argparse, shutil, os, sys, zipfile, requests, re, datetime, time
from sys import platform
from pathlib import Path

#Example Tor Browser target directory:
#   A:\\Tor' 'Browser' 'x64\\Tor' 'Browser

#Args
parser = argparse.ArgumentParser()

parser.add_argument("-g","--gpg", action="store_true", help="Download gpg windows installer to cwd")

#Commands to remove backups
parser.add_argument("-t","--date", type=str, help="Supply a backup by date that you want to remove")

#Commands to add backups
parser.add_argument("-d","--directory", type=str, help="Target directory you want to encrypt & backup")
parser.add_argument("-c","--compression", type=int, help="Specify the level of compression you want")
parser.add_argument("-u","--user", type=str, help="Username for MySQL")
parser.add_argument("-p","--password", type=str, help="Password for MySQL")

#Mutually Exclusive
group = parser.add_mutually_exclusive_group()
group.add_argument("-a","--add", action="store_true", help="Add a new backup to the database & backups directory")
group.add_argument("-r","--remove", action="store_true", help="Remove a backup from the database & backups directory")

args = parser.parse_args()

dir = args.directory
db = "torsync"
tb = "backups"

#Get the current date
currdate = "-" + str(datetime.datetime.today().strftime('%Y-%m-%d'))

#Gather where to put the GnuPG download
gnupg_dir = (os.getcwd() + (r"\gnupg-w32-2.2.11_20181106.exe"))

def create_db(user, password):
	dbconn = pymysql.connect("localhost", user, password)
	cursor = dbconn.cursor()
	#create pycryption database
	cursor.execute("CREATE DATABASE IF NOT EXISTS " + db)
	dbconn.commit()
	cursor.close()

def create_tb(user, password):
	dbconn = pymysql.connect("localhost", user, password)
	cursor = dbconn.cursor()
	#create backups table
	#create table fields & rows. Filename (15), date (char 10), Filetype (char 10), Filesize (int)
	cursor.execute("""CREATE TABLE IF NOT EXISTS """ + db + """.""" + tb + """ (
		Filename  VARCHAR(15),
		Date  VARCHAR(15),
		Filetype  VARCHAR(10),
		Filesize  INT
	)""")
	dbconn.commit()
	cursor.close()

def insert_tb(user, password, filename, date, filetype, filesize):
	dbconn = pymysql.connect("localhost", user, password)
	cursor = dbconn.cursor()
	use = "USE " + db + ";"
	insert = "INSERT INTO " + tb + " (Filename, Date, Filetype, Filesize) VALUES (\"{}\", \"{}\", \"{}\", \"{}\");".format(filename, date, filetype, str(filesize))
	check = "SELECT * FROM " + tb + ";"
	cursor.execute(use)
	cursor.execute(insert)
	cursor.execute(check)
	rows = cursor.fetchall()
	for row in rows:
		print(row)
	dbconn.commit()
	cursor.close()

def remove_tb(user, password, date):
	dbconn = pymysql.connect("localhost", user, password, db = "torsync")
	cursor = dbconn.cursor()
	delete = "DELETE FROM " + tb + " WHERE Date = '-" + date + "';"
	cursor.execute(delete)
	dbconn.commit()
	cursor.close()
	
#Download gpg installer to cwd
if args.gpg and sys.platform == "win32":

	html = requests.get("https://www.gnupg.org/download/")

	#Request has been successful
	if html.status_code == 200:

		html = requests.get("https://www.gnupg.org/download/").text
		ftp = re.search(r'\bftp\b/\bgcrypt/\bbinary/\bgnupg\b-\bw32-\d+.\d+.\d+_\d+.\bexe\b', html).group()
		filename = re.search(r'\bgnupg\b-\bw32-\d+.\d+.\d+_\d+.\bexe\b', html).group()
		url = "https://www.gnupg.org/" + ftp
		dwnld = requests.get(url)

		#Download latest GnuPG for w32
		request = open(filename, 'wb').write(dwnld.content)

	else:
		print("Could not find download url! Exiting...")
		sys.exit()

elif args.gpg and sys.platform == "linux":
	
	print("GnuPG comes installed on linux!")
	sys.exit()

elif args.gpg and sys.platform == "darwin":
	
	html = requests.get("https://sourceforge.net/p/gpgosx/docu/Download/")

	if html.status_code == 200:

		html = requests.get("https://sourceforge.net/p/gpgosx/docu/Download/").text
		ftp = re.search(r'\bprojects\b/\bgpgosx\b/\bfiles\b/\bGnuPG.\d+.\d+.\d+.\bdmg\b/\bdownload\b', html).group()
		filename = re.search(r'\bGnuPG.\d+.\d+.\d+.\bdmg\b/\bdownload\b', html).group()
		url = "https://sourceforge.net/" + ftp
		dwnld = requests.get(url)

		#Download gpgosx for MacOS
		request = open(filename, 'wb').write(dwnld.content)

	else:
		print("Could not find download url! Exiting...")
		sys.exit()

#Add new backup to database using directory + compression arg
elif args.add and args.directory and args.compression and args.compression > -1 and args.compression < 10 and args.user and args.password:
	print("Adding a new backup!")

	create_db(args.user, args.password)
	create_tb(args.user, args.password)

	bkdir = os.getcwd() + "/backups/Tor-Browser" + currdate

	#Handle duplicate files and folders
	if os.path.isdir(bkdir) == True:
		shutil.rmtree(bkdir)

	try:
		dir = shutil.copytree(dir, bkdir)
	except IOError as e:
		print("Cannot copy directory! Exiting...")
		shutil.rmtree(bkdir)
		sys.exit()

	#Zip file
	zip_file = dir + '.zip'

	#GPG file
	gpg_file = zip_file + '.gpg'

	if os.path.isfile(zip_file) == True:
		print("Found duplicate backup zip! Removing...")
		os.remove(zip_file)
	
	if os.path.isfile(gpg_file) == True:
		print("Found duplicate encrypted backup zip! Removing...")
		os.remove(gpg_file)

	print("zip_name: " + zip_file)

	#Zip up entire target directory
	def zip_directory(zip_file, dir):
		print("Zipping the target directory...")
		zip = zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED, compresslevel = args.compression)

		for dirname, subdirs, files in os.walk(dir):
			zip.write(dirname)
			for filename in files:
					zip.write(os.path.join(dirname, filename))

		print("Tor Browser backup zipped successfully!")
		zip.close()

	#Encrypt file using GPG
	def aes_encrypt(zip_file):
		
		#GPG --- C:\Users\Alex>gpg --sign --passphrase --symmetric --cipher-algo AES256 C:\Users\Alex\Desktop\pycryption\Tor-Browser-2018-11-23.zip
		print("Encrypting the zip file...")
		proc = subprocess.Popen(['gpg', '--sign', '--passphrase', '--symmetric', '--cipher-algo', 'AES256', zip_file])
		proc.communicate()[0]
		proc.returncode
		print(proc.returncode)
		print(type(proc.returncode))
		if proc == 1:
			proc.terminate()
			sys.exit()

		print("Encryption successful!")
	
	zip_directory(zip_file, dir)
	aes_encrypt(zip_file)
	os.remove(zip_file)
	shutil.rmtree(bkdir)

	#Get the size of the gpg file in MB
	try:
		size = os.path.getsize(gpg_file)
		filesize = (size >> 20)
	except FileNotFoundError as e:
		print("Encrypted zip file could not be found!\n   Exiting...")
		sys.exit()
	
	#Extract the gpg file name from the full path
	filename = re.search(r'\bTor\b-\bBrowser\b', gpg_file).group()
	filetype = re.search(r'.\bzip\b.\bgpg\b', gpg_file).group()

	#Get the GPG file
	print(filesize)
	insert_tb(args.user, args.password, filename, currdate, filetype, filesize)
	
	#Exit when finished
	sys.exit()

elif args.remove and args.user and args.password and args.date:
	print("Removing backup!")
	supplied = args.date
	if bool(re.match(r'\d\d\d\d-\d\d-\d\d', supplied)) == True:
		dir = os.getcwd() + "/backups/"
		os.chdir(dir)
		fullpath = dir + "Tor-Browser-" + supplied + ".zip.gpg"
		try:
			os.remove(str(fullpath))
			remove_tb(args.user, args.password, args.date)
		except IOError as e:
			print("File does not exist in backups directory!\n   Exiting...")
			sys.exit()
	else:
		err = print("Please provide arguments correctly!\nExample (1):\n   --gpg\nExample (2):\n   --add --directory A:\\Your\\target\\directory --compression (1-9) --user 'your_mysql_username' --password 'your_mysql_password'\nExample (3):\n   --remove --user 'your_mysql_username' --password 'your_mysql_password' --date 2018-12-26\n   Exiting...")
		sys.exit()
else:
	err = print("Please provide arguments correctly!\nExample (1):\n   --gpg\nExample (2):\n   --add --directory A:\\Your\\target\\directory --compression (1-9) --user 'your_mysql_username' --password 'your_mysql_password'\nExample (3):\n   --remove --user 'your_mysql_username' --password 'your_mysql_password' --date 2018-12-26\n   Exiting...")
	sys.exit()

'''print("File encrypted!")
time.sleep(5)
print("Decrypting now...")

enc_zip = (zip_name + '.gpg')

decrypt file takes in new gpg file and output file as parameters
def aes_decrypt(enc_zip,zip_name):
	subprocess.run(['gpg','--output',file,'--decrypt',zip_name])
	
aes_decrypt(file)

print("Decrypting complete!")'''

