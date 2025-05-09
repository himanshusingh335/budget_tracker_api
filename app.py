from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)
DB_NAME = "budget.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def format_currency(value):
    return f"₹ {value:.2f}"

@app.route("/summary/<int:month>/<int:year>", methods=["GET"])
def get_summary(month, year):
    month_year = f"{month:02d}/{str(year)[-2:]}"  # e.g., 4/2024 → "04/24"
    conn = get_db_connection()

    # Get budget
    budget_cursor = conn.execute(
        "SELECT Category, Budget FROM budget_set WHERE MonthYear = ?", (month_year,)
    )
    budget_data = {row["Category"]: row["Budget"] for row in budget_cursor.fetchall()}

    # Get expenditures
    exp_cursor = conn.execute(
        "SELECT Category, SUM(Expenditure) as Total FROM budget_tracker WHERE Month = ? AND Year = ? GROUP BY Category",
        (month, year),
    )
    exp_data = {row["Category"]: row["Total"] for row in exp_cursor.fetchall()}

    if not budget_data:
        return jsonify({"error": "No budget data found for this month"}), 404

    summary = []
    total_budget = 0
    total_expense = 0

    all_categories = set(budget_data.keys()).union(exp_data.keys())

    for category in sorted(all_categories):
        budget = budget_data.get(category, 0)
        expense = exp_data.get(category, 0)
        diff = budget - expense

        total_budget += budget
        total_expense += expense

        summary.append({
            "MonthYear": month_year,
            "Category": category,
            "Budget": format_currency(budget),
            "Expenditure": format_currency(expense),
            "Difference": format_currency(diff)
        })

    summary.append({
        "MonthYear": "Total",
        "Category": "",
        "Budget": format_currency(total_budget),
        "Expenditure": format_currency(total_expense),
        "Difference": format_currency(total_budget - total_expense)
    })

    conn.close()
    return jsonify(summary)

@app.route("/transactions/<int:month>/<int:year>", methods=["GET"])
def get_transactions(month, year):
    conn = get_db_connection()
    cursor = conn.execute(
        "SELECT * FROM budget_tracker WHERE Month = ? AND Year = ?", (month, year)
    )
    transactions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(transactions)

@app.route("/expenditures", methods=["POST"])
def add_expenditure():
    data = request.json
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO budget_tracker (Date, Description, Category, Expenditure, Year, Month, Day) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            data["Date"],
            data["Description"],
            data["Category"],
            data["Expenditure"],
            data["Year"],
            data["Month"],
            data["Day"],
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Expenditure added successfully"}), 201

@app.route("/budget", methods=["POST"])
def add_budget():
    data = request.json
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO budget_set (MonthYear, Category, Budget) VALUES (?, ?, ?)",
        (data["MonthYear"], data["Category"], data["Budget"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Budget entry added successfully"}), 201

@app.route("/expenditures/<int:id>", methods=["DELETE"])
def delete_expenditure(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM budget_tracker WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Expenditure deleted successfully"}), 200

@app.route("/budget", methods=["DELETE"])
def delete_budget():
    data = request.json
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM budget_set WHERE MonthYear = ? AND Category = ?",
        (data["MonthYear"], data["Category"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Budget entry deleted successfully"}), 200

if __name__ == "__main__":
    app.run(debug=True)