import io
import hashlib
import pandas as pd
import streamlit as st
from supabase import create_client, Client

# --- SUPABASE CONNECTION SETUP ---
# Ensure these keys exist in your .streamlit/secrets.toml or Streamlit Cloud Secrets
SUPABASE_URL = st.secrets.get("supabase_url", "")
SUPABASE_KEY = st.secrets.get("supabase_key", "")

@st.cache_resource
def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("❌ Supabase secrets are missing! Check your secrets.toml file.")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase_client()

# Standard database columns
REQUIRED_COLUMNS = ["id", "class", "subject", "period", "semester", "grade", "password_hash"]

def hash_password(password: str) -> str:
    """Hash password string using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

# --- STREAMLIT UI SETUP ---
st.set_page_config(page_title="Academic Records Portal", layout="wide")
st.title("🏫 Academic Records Portal")
st.write("Welcome to the Student and Admin Grades Management System.")

tab_student, tab_admin = st.tabs(["🎓 Student Portal", "🔐 Admin Dashboard"])

# --- STUDENT PORTAL ---
with tab_student:
    st.header("Student Grade Inquiry")
    
    col_input1, col_input2 = st.columns(2)
    with col_input1:
        student_id = st.text_input("Enter Student ID:", key="stu_id_input").strip()
    with col_input2:
        student_pass = st.text_input("Enter Password:", type="password", key="stu_pass_input").strip()
    
    auth_key = f"authenticated_{student_id}"
    
    if st.button("Access Dashboard", key="btn_student_login"):
        if student_id and student_pass:
            hashed_input = hash_password(student_pass)
            
            # Authenticate directly against Supabase database
            try:
                response = supabase.table("grades") \
                    .select("id") \
                    .eq("id", student_id) \
                    .eq("password_hash", hashed_input) \
                    .execute()
                
                if response.data:
                    st.success(f"✅ Welcome Back, Student ID: {student_id}")
                    st.session_state[auth_key] = True
                else:
                    st.error("❌ Invalid Student ID or Password.")
                    st.session_state[auth_key] = False
            except Exception as e:
                st.error(f"❌ Database error: {str(e)}")
        else:
            st.warning("⚠️ Both Student ID and Password are required.")

    # Render dashboard if session is authenticated
    if st.session_state.get(auth_key, False):
        try:
            student_data = supabase.table("grades").select("*").eq("id", student_id).execute()
            student_rows = pd.DataFrame(student_data.data)
            
            if not student_rows.empty:
                student_rows['grade'] = pd.to_numeric(student_rows['grade'], errors='coerce')
                
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    semesters = ["All Semesters"] + sorted(student_rows['semester'].dropna().astype(str).unique().tolist())
                    selected_semester = st.selectbox("Filter by Semester", semesters, key="student_sem_filter")
                with col_f2:
                    periods = ["All Periods"] + sorted(student_rows['period'].dropna().astype(str).unique().tolist())
                    selected_period = st.selectbox("Filter by Period", periods, key="student_per_filter")
                
                filtered_df = student_rows.copy()
                if selected_semester != "All Semesters":
                    filtered_df = filtered_df[filtered_df['semester'].astype(str) == selected_semester]
                if selected_period != "All Periods":
                    filtered_df = filtered_df[filtered_df['period'].astype(str) == selected_period]
                    
                st.subheader("📊 Academic Performance Summary")
                metric_col1, metric_col2, metric_col3 = st.columns(3)
                
                current_avg = filtered_df['grade'].mean()
                with metric_col1:
                    if pd.isna(current_avg):
                        st.metric(label="Current Filtered Average", value="N/A")
                    else:
                        st.metric(label="Current Filtered Average", value=f"{current_avg:.2f}%")
                        
                with metric_col2:
                    st.markdown("**Average by Semester**")
                    sem_avg = student_rows.groupby('semester')['grade'].mean().reset_index()
                    for _, row in sem_avg.iterrows():
                        st.write(f"• **{row['semester']}**: {row['grade']:.2f}%")
                        
                with metric_col3:
                    st.markdown("**Average by Period**")
                    per_avg = student_rows.groupby('period')['grade'].mean().reset_index()
                    for _, row in per_avg.iterrows():
                        st.write(f"• **{row['period']}**: {row['grade']:.2f}%")
                
                st.divider()
                st.subheader("Your Academic Record")
                display_df = filtered_df.drop(columns=['password_hash', 'created_at'], errors='ignore')
                st.dataframe(display_df, use_container_width=True)
                
                # --- EXPORT & DOWNLOAD ---
                dl_col1, dl_col2 = st.columns(2)
                with dl_col1:
                    csv_buffer = io.StringIO()
                    display_df.to_csv(csv_buffer, index=False)
                    st.download_button(
                        label="📥 Download Filtered Transcript (CSV)",
                        data=csv_buffer.getvalue(),
                        file_name=f"Transcript_{student_id}.csv",
                        mime="text/csv",
                        key="dl_student_csv"
                    )
                    
                with dl_col2:
                    txt_report = [
                        "=========================================",
                        "         OFFICIAL REPORT CARD            ",
                        "=========================================",
                        f"Student ID : {student_id}"
                    ]
                    if not display_df.empty and 'class' in display_df.columns:
                        txt_report.append(f"Class      : {display_df['class'].iloc[0]}")
                    txt_report.append(f"Filters    : {selected_semester} | {selected_period}")
                    txt_report.append("-----------------------------------------")
                    
                    avg_str = f"{current_avg:.2f}%" if not pd.isna(current_avg) else "N/A"
                    txt_report.append(f"Overall Filtered Average: {avg_str}\n\nSummary by Semester:")
                    for _, row in sem_avg.iterrows():
                        txt_report.append(f" - {row['semester']}: {row['grade']:.2f}%")
                    txt_report.append("\nSummary by Period:")
                    for _, row in per_avg.iterrows():
                        txt_report.append(f" - {row['period']}: {row['grade']:.2f}%")
                        
                    txt_report.append("-----------------------------------------")
                    txt_report.append(f"{'Subject':<18} | {'Semester':<10} | {'Period':<10} | {'Grade':<5}")
                    txt_report.append("-" * 53)
                    
                    for _, row in display_df.iterrows():
                        txt_report.append(
                            f"{str(row.get('subject', '')):<18} | "
                            f"{str(row.get('semester', '')):<10} | "
                            f"{str(row.get('period', '')):<10} | "
                            f"{str(row.get('grade', '')):<5}"
                        )
                    txt_report.append("=========================================")
                    
                    st.download_button(
                        label="📄 Download Report Card (TXT)",
                        data="\n".join(txt_report),
                        file_name=f"ReportCard_{student_id}.txt",
                        mime="text/plain",
                        key="dl_student_txt"
                    )
            else:
                st.info("💡 You are authenticated, but no grade records were found.")
        except Exception as e:
            st.error(f"❌ Error fetching student data: {str(e)}")

# --- ADMIN DASHBOARD ---
with tab_admin:
    st.header("Administrative Access Gate")
    if "admin_authenticated" not in st.session_state:
        st.session_state["admin_authenticated"] = False
        
    if not st.session_state["admin_authenticated"]:
        admin_user = st.text_input("Username:", key="admin_user_input")
        admin_pass = st.text_input("Password:", type="password", key="admin_pass_input")
        if st.button("Authenticate Admin", key="btn_admin_login"):
            # Update credentials as needed for production
            if admin_user == "admin" and admin_pass == "password123":
                st.session_state["admin_authenticated"] = True
                st.rerun()
            else:
                st.error("❌ Invalid Admin Username or Password.")
    else:
        st.success("✅ Admin Authentication Successful. Live database loaded below.")
        if st.button("🚪 Logout Admin Panel", key="btn_admin_logout"):
            st.session_state["admin_authenticated"] = False
            st.rerun()
            
        st.divider()
        st.subheader("Bulk Record Upload")
        uploaded_file = st.file_uploader("Upload grades update file (.csv)", type=["csv"], key="csv_uploader")
        
        if uploaded_file is not None:
            try:
                uploaded_df = pd.read_csv(uploaded_file)
                uploaded_df.columns = [c.strip().lower() for c in uploaded_df.columns]
                
                # Check required columns (excluding password_hash if auto-generated)
                base_required = ["id", "class", "subject", "period", "semester", "grade"]
                missing = [col for col in base_required if col not in uploaded_df.columns]
                
                if missing:
                    st.error(f"❌ Upload Rejected. Missing target columns: {', '.join(missing)}")
                else:
                    if "password_hash" not in uploaded_df.columns:
                        uploaded_df["password_hash"] = uploaded_df["id"].apply(lambda x: hash_password(str(x)))
                    
                    final_df = uploaded_df[REQUIRED_COLUMNS]
                    records = final_df.to_dict(orient="records")
                    
                    # Insert records safely into Supabase
                    supabase.table("grades").insert(records).execute()
                    st.success(f"🎉 Success! Uploaded {len(records)} records to Supabase.")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Engine parsing error: {str(e)}")
                
        st.subheader("📝 Live Master Records Editor")
        st.caption("Double-click any cell to edit data or insert rows. Remember to save changes below.")
        
        try:
            master_data = supabase.table("grades").select("*").execute()
            master_df = pd.DataFrame(master_data.data)
            
            if not master_df.empty:
                if 'created_at' in master_df.columns:
                    master_df = master_df.drop(columns=['created_at'])
                    
                edited_df = st.data_editor(
                    master_df, 
                    use_container_width=True, 
                    num_rows="dynamic",
                    key="admin_records_editor"
                )
                
                admin_col1, admin_col2 = st.columns(2)
                
                with admin_col1:
                    if st.button("💾 Save Table Changes", key="btn_save_changes"):
                        try:
                            # Auto-fill missing password hashes using Student ID
                            for index, row in edited_df.iterrows():
                                if pd.isna(row['password_hash']) or str(row['password_hash']).strip() == "":
                                    edited_df.at[index, 'password_hash'] = hash_password(str(row['id']))
                            
                            updated_records = edited_df.to_dict(orient="records")
                            
                            # Safe overwrite: Delete using wildcard match on non-empty IDs
                            supabase.table("grades").delete().neq("id", "___TEMP_RESERVED_KEY___").execute()
                            if updated_records:
                                supabase.table("grades").insert(updated_records).execute()
                                
                            st.success("🎉 Database saved successfully to Supabase!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error saving database changes: {str(e)}")
                
                with admin_col2:
                    admin_csv_buffer = io.StringIO()
                    master_df.to_csv(admin_csv_buffer, index=False)
                    st.download_button(
                        label="📥 Download Master Database (CSV)",
                        data=admin_csv_buffer.getvalue(),
                        file_name="master_grades_database.csv",
                        mime="text/csv",
                        key="admin_download_btn"
                    )
            else:
                st.info("💡 The Supabase database table is currently empty.")
        except Exception as e:
            st.error(f"❌ Error loading master database: {str(e)}")