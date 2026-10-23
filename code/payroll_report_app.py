"""
payroll_report_app.py — the quarter at a glance, for someone who never opens a terminal.

Every Friday since September the office manager at Salt City Coffee has downloaded
a payroll export from the Assignment 04 app; before that she typed the same file
by hand. The owner now wants to know where the hours went this quarter, the
accountant wants pay by month and department, and the manager wants to see who
has been missing shifts. This page answers all three from the pile of exports.

Same shape as Assignment 04: the page *assembles* the pipeline — one call to
`build_history` does the cleaning — and then shows the reports, filtered by the
department and dates the user picks.

Run it:  Run and Debug -> "Streamlit Run: Current File"
Test it: pytest tests/test_pipeline.py -k app
"""

import streamlit as st

from payroll.extract import load_employees, load_export
from payroll.reshape import hours_grid, missed_weeks, pay_by_month
from payroll.summarize import build_history, summarize_employees

st.title("Salt City Coffee — Quarterly Payroll Report")
st.write(
    "Upload the weekly payroll exports for the quarter. Then pick a department "
    "and a date range to see hours, pay and missed weeks."
)

roster = load_employees()

uploads = st.file_uploader(
    "Weekly payroll exports (CSV)",
    type="csv",
    accept_multiple_files=True,
    key="exports",
)

if uploads:
    history = build_history([load_export(u) for u in uploads], roster)

    # Rows whose ID is not on the roster have no department: warn and leave them out.
    unmatched = history["department"].isna()
    if unmatched.any():
        raw_ids = history.loc[unmatched, "employeeid"].str.strip()
        clean_ids = history.loc[unmatched, "employee_id"]
        missing_ids = sorted(set(raw_ids) | set(clean_ids))
        st.warning(
            "These employeeids are not on the roster and are left out of the "
            "report: " + ", ".join(missing_ids)
        )
    matched = history[~unmatched]

    # Filters
    departments = ["All"] + sorted(matched["department"].unique())
    department = st.selectbox("Department", departments, key="department")

    first_day = matched["pay_date"].min().date()
    last_day = matched["pay_date"].max().date()
    dates = st.date_input(
        "Pay dates",
        value=(first_day, last_day),
        min_value=first_day,
        max_value=last_day,
        key="dates",
    )
    # While the user is still picking, date_input returns only the start date.
    if isinstance(dates, (list, tuple)) and len(dates) == 2:
        start, end = dates
    elif isinstance(dates, (list, tuple)) and len(dates) == 1:
        start = end = dates[0]
    else:
        start = end = dates

    selected = matched
    if department != "All":
        selected = selected[selected["department"] == department]
    pay_days = selected["pay_date"].dt.date
    selected = selected[(pay_days >= start) & (pay_days <= end)]

    st.subheader(f"{department}: {start} to {end}")

    if selected.empty:
        st.info("No payroll rows match this department and date range.")
    else:
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Weeks", selected["week_ending"].nunique())
        col2.metric("Employees", selected["employee_id"].nunique())
        col3.metric("Total hours", f"{selected['hours_worked'].sum():,.2f}")
        col4.metric("Total gross pay", f"${selected['gross_pay'].sum():,.2f}")

        # Pay by month and department
        monthly = pay_by_month(selected)
        st.subheader("Gross pay by month and department")
        st.bar_chart(monthly, x="month")

        # Reports
        st.subheader("Employee summary")
        st.dataframe(summarize_employees(selected), hide_index=True)

        grid = hours_grid(selected)
        st.subheader("Hours by week")
        st.dataframe(grid, hide_index=True)

        st.subheader("Missed weeks")
        st.dataframe(missed_weeks(grid), hide_index=True)

        st.download_button(
            "Download pay by month (CSV)",
            data=monthly.to_csv(index=False),
            file_name="pay_by_month.csv",
            mime="text/csv",
            key="download",
        )