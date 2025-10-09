package main

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"strconv"
	"strings"

	_ "github.com/go-sql-driver/mysql"
	"github.com/gorilla/mux"
)

var (
	db           *sql.DB
	departmentID = map[string]int{
		"AIML": 0,
		"CSE":  1,
		"ISE":  2,
		"EC":   3,
		"MECH": 4,
	}
	departmentIDReverse = map[int]string{
		0: "AIML",
		1: "CSE",
		2: "ISE",
		3: "EC",
		4: "MECH",
	}
)

func initDB() error {
	var err error
	dsn := "root:2787@tcp(localhost:3306)/RESEARCH_PAPER_REPO1?charset=utf8mb4&collation=utf8mb4_general_ci"
	db, err = sql.Open("mysql", dsn)
	if err != nil {
		return err
	}

	if err = db.Ping(); err != nil {
		return err
	}

	log.Println("Database connected successfully")

	createTableSQL := `CREATE TABLE IF NOT EXISTS users (
		id INT AUTO_INCREMENT PRIMARY KEY,
		username VARCHAR(255) UNIQUE,
		password VARCHAR(255)
	)`
	_, err = db.Exec(createTableSQL)
	return err
}

func hashPassword(password string) string {
	hash := sha256.Sum256([]byte(password))
	return hex.EncodeToString(hash[:])
}

func loginRedirect(w http.ResponseWriter, r *http.Request) {
	http.Redirect(w, r, "/Templates", http.StatusFound)
}

func landingPage(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodPost {
		http.Redirect(w, r, "/login", http.StatusFound)
		return
	}
	tmpl := template.Must(template.ParseFiles("Templates/landing_page.html"))
	tmpl.Execute(w, nil)
}

func login(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodPost {
		username := r.FormValue("username")
		password := r.FormValue("password")

		if username == "" {
			tmpl := template.Must(template.ParseFiles("Templates/login.html"))
			tmpl.Execute(w, map[string]string{"message": "haha, i fixed that bug hahahaha"})
			return
		}

		var storedPassword string
		err := db.QueryRow("SELECT password FROM users WHERE username=?", username).Scan(&storedPassword)

		if err == sql.ErrNoRows {
			tmpl := template.Must(template.ParseFiles("Templates/login.html"))
			tmpl.Execute(w, map[string]string{"message": "Invalid username"})
			return
		} else if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		if hashPassword(password) == storedPassword {
			tmpl := template.Must(template.ParseFiles("Templates/home.html"))
			tmpl.Execute(w, nil)
		} else {
			tmpl := template.Must(template.ParseFiles("Templates/login.html"))
			tmpl.Execute(w, map[string]string{"message": "Invalid password"})
		}
		return
	}

	tmpl := template.Must(template.ParseFiles("Templates/login.html"))
	tmpl.Execute(w, nil)
}

func createUser(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodPost {
		newUsername := r.FormValue("new_username")
		newPassword := r.FormValue("new_password")

		if newUsername == "" || newUsername == newPassword {
			tmpl := template.Must(template.ParseFiles("Templates/create_user.html"))
			tmpl.Execute(w, map[string]string{"message": "invalid entry!!!"})
			return
		}

		hashedPassword := hashPassword(newPassword)
		_, err := db.Exec("INSERT INTO users (username, password) VALUES (?, ?)", newUsername, hashedPassword)

		if err != nil {
			if strings.Contains(err.Error(), "Duplicate entry") {
				tmpl := template.Must(template.ParseFiles("Templates/create_user.html"))
				tmpl.Execute(w, map[string]string{"message": "Username already exists"})
				return
			}
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}

		http.Redirect(w, r, "/login", http.StatusFound)
		return
	}

	tmpl := template.Must(template.ParseFiles("Templates/create_user.html"))
	tmpl.Execute(w, nil)
}

func admin(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodPost {
		department := r.FormValue("department")
		info := r.FormValue("info")

		if department != "" {
			deptID, ok := departmentID[department]
			if !ok {
				http.Error(w, "Invalid department", http.StatusBadRequest)
				return
			}

			tables := []string{"JOURNAL", "CONFERENCE", "BOOKCHAPTER", "FUNDEDRESEARCHPROJECT",
				"RESEARCHPROPOSALSUBMITTED", "CONSULTANCY", "PRODUCTDEVELOPMENT", "PATENT",
				"FDPWORKSHOPSEMINAR", "MOUCS", "ACHIEVEMENTSANDAWARDS", "MOUS", "FUNDEDSTUDENTPROJECT"}

			var counts []string
			for _, table := range tables {
				var count int
				err := db.QueryRow(fmt.Sprintf("SELECT COUNT(*) FROM %s WHERE DEPARTMENT_ID=?", table), deptID).Scan(&count)
				if err != nil {
					counts = append(counts, "0")
				} else {
					counts = append(counts, strconv.Itoa(count))
				}
			}

			tmpl := template.Must(template.ParseFiles("Templates/admin.html"))
			tmpl.Execute(w, map[string]interface{}{
				"counts":         strings.Join(counts, ","),
				"selected_table": nil,
			})
			return
		}

		if info != "" {
			infoType := strings.ToUpper(info)
			filterOption := strings.ToUpper(r.FormValue("filter"))
			textInput := strings.ToUpper(r.FormValue("text-input"))

			var rows *sql.Rows
			var err error

			if filterOption == textInput {
				rows, err = db.Query(fmt.Sprintf("SELECT * FROM %s", infoType))
			} else if filterOption == "DEPARTMENT" {
				deptID, ok := departmentID[textInput]
				if !ok {
					http.Error(w, "Invalid department", http.StatusBadRequest)
					return
				}
				rows, err = db.Query(fmt.Sprintf("SELECT * FROM %s WHERE DEPARTMENT_ID = ?", infoType), deptID)
			} else {
				rows, err = db.Query(fmt.Sprintf("SELECT * FROM %s WHERE %s = ?", infoType, filterOption), textInput)
			}

			if err != nil {
				http.Error(w, err.Error(), http.StatusInternalServerError)
				return
			}
			defer rows.Close()

			columns, _ := rows.Columns()
			var data [][]interface{}

			for rows.Next() {
				values := make([]interface{}, len(columns))
				valuePtrs := make([]interface{}, len(columns))
				for i := range values {
					valuePtrs[i] = &values[i]
				}

				if err := rows.Scan(valuePtrs...); err != nil {
					continue
				}

				row := make([]interface{}, len(values))
				for i, v := range values {
					if i == 0 {
						if deptID, ok := v.(int64); ok {
							row[i] = departmentIDReverse[int(deptID)]
						} else {
							row[i] = v
						}
					} else {
						row[i] = v
					}
				}
				data = append(data, row)
			}

			tmpl := template.Must(template.ParseFiles("Templates/admin.html"))
			tmpl.Execute(w, map[string]interface{}{
				"data":           data,
				"selected_table": infoType,
			})
			return
		}
	}

	tmpl := template.Must(template.ParseFiles("Templates/admin.html"))
	tmpl.Execute(w, nil)
}

func user(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodPost {
		department := r.FormValue("department")
		deptID, ok := departmentID[department]
		if !ok {
			tmpl := template.Must(template.ParseFiles("Templates/user.html"))
			tmpl.Execute(w, map[string]string{"message": "Invalid department"})
			return
		}

		r.ParseForm()

		// Journal
		if r.FormValue("Journal-Authors") != "" {
			_, err := db.Exec(`INSERT INTO JOURNAL(DEPARTMENT_ID, AUTHORS, YEAR_OF_PUBLICATION, TITLE, JOURNAL_NAME, VOLUME_PAGE_NUMBER, ISSN, IMPACT_FACTOR) 
				VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
				deptID,
				r.FormValue("Journal-Authors"),
				r.FormValue("Journal-Year of publication"),
				r.FormValue("Journal-Title"),
				r.FormValue("Journal-Journal name"),
				r.FormValue("Journal-Volume and page number"),
				r.FormValue("Journal-ISSN"),
				r.FormValue("Journal-Impact factor"))
			if err != nil {
				log.Println("Error inserting journal:", err)
			} else {
				log.Println("Journal data entered successfully!")
			}
		}

		// Conference
		if r.FormValue("Conference-Authors") != "" {
			_, err := db.Exec(`INSERT INTO CONFERENCE(DEPARTMENT_ID, YEAR_OF_PUBLICATION, AUTHOR, TITLE, CONFERENCE_NAME, VOLUME_PAGE_COUNT, ORGANIZED_BY, PLACE_OF_CONFERENCE) 
				VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
				deptID,
				r.FormValue("Conference-Year of publication"),
				r.FormValue("Conference-Authors"),
				r.FormValue("Conference-Title"),
				r.FormValue("Conference-Conference Name"),
				r.FormValue("Conference-Volume and page count"),
				r.FormValue("Conference-Organized by"),
				r.FormValue("Conference-Place of conference"))
			if err != nil {
				log.Println("Error inserting conference:", err)
			} else {
				log.Println("Conference data entered successfully!")
			}
		}

		// BookChapter
		if r.FormValue("BookChapter-Authors") != "" {
			_, err := db.Exec(`INSERT INTO BOOKCHAPTER(DEPARTMENT_ID, YEAR_OF_PUBLICATION, AUTHOR, CHAPTER_TITLE, BOOK_TITLE, PUBLISHER, ISSN) 
				VALUES (?, ?, ?, ?, ?, ?, ?)`,
				deptID,
				r.FormValue("BookChapter-Year of publication"),
				r.FormValue("BookChapter-Authors"),
				r.FormValue("BookChapter-Chapter title"),
				r.FormValue("BookChapter-Book title"),
				r.FormValue("BookChapter-Publisher"),
				r.FormValue("BookChapter-ISSN"))
			if err != nil {
				log.Println("Error inserting book chapter:", err)
			} else {
				log.Println("Book chapter data entered successfully!")
			}
		}

		// Add similar blocks for other tables following the same pattern...
		// FundedResearchProject, ResearchProposalSubmitted, Consultancy, ProductDevelopment, Patent, etc.

		tmpl := template.Must(template.ParseFiles("Templates/user.html"))
		tmpl.Execute(w, map[string]string{"message": "Data submitted successfully!"})
		return
	}

	tmpl := template.Must(template.ParseFiles("Templates/user.html"))
	tmpl.Execute(w, map[string]string{"message": "Input not found"})
}

func main() {
	if err := initDB(); err != nil {
		log.Fatal("Failed to connect to database:", err)
	}
	defer db.Close()

	r := mux.NewRouter()
	r.HandleFunc("/", loginRedirect)
	r.HandleFunc("/Templates", landingPage).Methods("GET", "POST")
	r.HandleFunc("/login", login).Methods("GET", "POST")
	r.HandleFunc("/create_user", createUser).Methods("GET", "POST")
	r.HandleFunc("/admin", admin).Methods("GET", "POST")
	r.HandleFunc("/user", user).Methods("GET", "POST")

	log.Println("Server starting on :5000")
	log.Fatal(http.ListenAndServe(":5000", r))
}
