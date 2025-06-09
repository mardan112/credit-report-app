import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import re
from io import BytesIO
import streamlit.components.v1 as components

def extract_text_from_pdf(uploaded_file):
    text = ""
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text

def extract_section(text, bureau):
    start = text.find(bureau)
    if start == -1:
        return ""
    next_bureaus = ["TransUnion", "Experian", "Equifax"]
    next_bureaus.remove(bureau)
    next_indices = [text.find(nb, start + 1) for nb in next_bureaus if text.find(nb, start + 1) != -1]
    end = min(next_indices) if next_indices else len(text)
    return text[start:end]

def parse_accounts(text):
    pattern = r"(?P<creditor>[A-Z0-9\-/ &]+)\s+Account #:.*?(?:TransUnion|Experian|Equifax)\s+Account Type: (?P<type>.*?)\s+.*?Account Status: (?P<status>.*?)\s+Monthly Payment: \$(?P<monthly_payment>[\d,.]+|0.00)\s+Date Opened: (?P<date_opened>\d{2}/\d{2}/\d{4}|\d{2}/\d{4}|N/A)\s+Balance: \$(?P<balance>[\d,.]+|0.00)\s+No. of Months \(terms\): (?P<terms>\d+|0)\s+High Credit: \$(?P<high_credit>[\d,.]+|0.00)\s+Credit Limit: \$(?P<limit>[\d,.]+|0.00|N/A)\s+.*?Authorized User"
    matches = re.finditer(pattern, text, re.DOTALL)
    data = []
    for match in matches:
        groups = match.groupdict()
        data.append({
            "Creditor": groups['creditor'].strip(),
            "Type": groups['type'].strip(),
            "Status": groups['status'].strip(),
            "Monthly Payment": groups['monthly_payment'].replace(",", ""),
            "Date Opened": groups['date_opened'],
            "Balance": groups['balance'].replace(",", ""),
            "Terms": groups['terms'],
            "High Credit": groups['high_credit'].replace(",", ""),
            "Credit Limit": groups['limit'].replace(",", "")
        })
    return pd.DataFrame(data)

def restructure_to_vertical(df):
    rows = []
    for i, row in df.iterrows():
        label = f"Account {i+1} ({row['Status'].upper()} - {row['Type'].title()})"
        if "open" in row['Status'].lower():
            styled_label = f"<div style='color: limegreen; font-weight: bold; font-family: Arial, sans-serif;'>{label}</div>"
        else:
            styled_label = f"<div style='color: #555555; background-color: #e0e0e0; font-weight: bold; font-family: Arial, sans-serif;'>{label}</div>"
        rows.append(("---", styled_label))
        for col in df.columns:
            rows.append((col, row[col]))
    return rows

def sort_accounts(df):
    open_df = df[df['Status'].str.lower().str.contains("open")].copy()
    closed_df = df[df['Status'].str.lower().str.contains("closed")].copy()
    return pd.concat([open_df, closed_df], ignore_index=True)

st.title("📄 Credit Report Categorizer")
st.markdown("Drop your credit report PDF below and select which bureau(s) to audit.")

uploaded_file = st.file_uploader("Upload IdentityIQ Credit Report (PDF)", type=["pdf"])
bureaus = st.multiselect("Which bureau(s) do you want to audit?", ["Equifax", "TransUnion", "Experian"], default=["Equifax"])

if uploaded_file and bureaus:
    raw_text = extract_text_from_pdf(uploaded_file)
    full_results = []

    for bureau in bureaus:
        bureau_text = extract_section(raw_text, bureau)

        if bureau_text:
            st.success(f"{bureau} section extracted successfully!")
            df = parse_accounts(bureau_text)

            if not df.empty:
                df["Bureau"] = bureau
                full_results.append(df)
            else:
                st.warning(f"No accounts found in {bureau} section.")
        else:
            st.error(f"Could not find {bureau} section in the uploaded file.")

    if full_results:
        combined_df = pd.concat(full_results, ignore_index=True)
        sorted_df = sort_accounts(combined_df)
        vertical_rows = restructure_to_vertical(sorted_df)

        st.write("### 📊 Organized Vertical Account Summary")
        for field, value in vertical_rows:
            if field == "---":
                st.markdown(value, unsafe_allow_html=True)
            else:
                st.write(f"**{field}:** {value}")

        # Export to Excel
        df_for_export = pd.DataFrame(vertical_rows, columns=["Field", "Value"])
        output = BytesIO()
        df_for_export.to_excel(output, index=False)
        st.download_button("📥 Download Vertical Excel Report", data=output.getvalue(), file_name="credit_vertical_summary.xlsx")
