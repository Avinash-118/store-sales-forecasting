import os
import requests
import pandas as pd
import streamlit as st

import state


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Store Sales Forecasting",
    page_icon="📊",
    layout="wide"
)


# ============================================================
# EXTERNAL STATE (PostgreSQL + Key Vault + Blob Storage)
# ============================================================

API_URL = os.getenv("API_URL", "http://api:8000/")


@st.cache_resource
def init_database():
    """Apply SQL migrations once per container start."""
    state.run_migrations()
    return True


try:
    init_database()
    db_ready = True
    db_startup_error = ""
except Exception as startup_error:
    db_ready = False
    db_startup_error = str(startup_error)


# ============================================================
# HEADER
# ============================================================

st.title("📊 Store Sales Forecasting")

st.markdown(
    """
    Predict future store sales using a machine-learning forecasting model.

    Select the store, product family, forecast horizon,
    promotion information, and holiday information below.
    """
)

st.divider()


# ============================================================
# INPUT SECTION
# ============================================================

st.header("⚙️ Forecast Settings")

col1, col2 = st.columns(2)

with col1:

    store_nbr = st.number_input(
        "Store Number",
        min_value=1,
        max_value=54,
        value=1,
        step=1
    )

with col2:

    family = st.selectbox(
        "Product Family",
        [
            "AUTOMOTIVE",
            "BABY CARE",
            "BEAUTY",
            "BEVERAGES",
            "BOOKS",
            "BREAD/BAKERY",
            "CELEBRATION",
            "CLEANING",
            "DAIRY",
            "DELI",
            "EGGS",
            "FROZEN FOODS",
            "GROCERY I",
            "GROCERY II",
            "HARDWARE",
            "HOME AND KITCHEN I",
            "HOME AND KITCHEN II",
            "HOME APPLIANCES",
            "HOME CARE",
            "LADIESWEAR",
            "LAWN AND GARDEN",
            "LINGERIE",
            "LIQUOR,WINE,BEER",
            "MAGAZINES",
            "MEATS",
            "PERSONAL CARE",
            "PET SUPPLIES",
            "PLAYERS AND ELECTRONICS",
            "POULTRY",
            "PREPARED FOODS",
            "PRODUCE",
            "SCHOOL AND OFFICE SUPPLIES",
            "SEAFOOD"
        ]
    )


# ============================================================
# FORECAST HORIZON
# ============================================================

horizon = st.slider(
    "Forecast horizon (days)",
    min_value=1,
    max_value=30,
    value=7
)


# ============================================================
# PROMOTION INPUT
# ============================================================

st.subheader("🏷️ Promotion count per day")

st.caption(
    "Enter the number of promoted items expected for each forecast day."
)

promotion_cols = st.columns(horizon)

onpromotion = []

for i in range(horizon):

    with promotion_cols[i]:

        promo = st.number_input(
            f"D{i + 1}",
            min_value=0,
            value=0,
            step=1,
            key=f"promo_{i}"
        )

        onpromotion.append(int(promo))


# ============================================================
# HOLIDAY INPUT
# ============================================================

st.subheader("📅 Holiday flag per day")

st.caption(
    "Check the box if that day is a public holiday or local event day. "
    "Holidays can push sales up or down depending on the category."
)

holiday_cols = st.columns(horizon)

is_holiday = []

for i in range(horizon):

    with holiday_cols[i]:

        holiday = st.checkbox(
            f"D{i + 1}",
            key=f"holiday_{i}"
        )

        is_holiday.append(1 if holiday else 0)


# ============================================================
# RUN FORECAST
# ============================================================

st.write("")

if st.button(
    "🔮 Run Forecast",
    type="primary"
):

    payload = {
        "store_nbr": int(store_nbr),
        "family": family,
        "horizon": int(horizon),
        "onpromotion": onpromotion,
        "is_holiday": is_holiday
    }

    with st.spinner("Calling the forecasting model..."):

        try:

            # API_URL comes from an environment variable (see top of file).
            response = requests.post(
                API_URL,
                json=payload,
                timeout=120
            )

            response.raise_for_status()

            predictions = response.json()

            # Handle APIs that return a dictionary.
            if isinstance(predictions, dict):

                if "predictions" in predictions:
                    predictions = predictions["predictions"]

                elif "forecast" in predictions:
                    predictions = predictions["forecast"]

                elif "sales" in predictions:
                    predictions = predictions["sales"]

            if not isinstance(predictions, list):
                raise ValueError(
                    f"Unexpected API response: {predictions}"
                )

            # Make sure values can be displayed/stored.
            predictions = [
                float(value)
                for value in predictions
            ]

            st.success("Forecast generated!")

            # ==================================================
            # RESULTS DATAFRAME
            # ==================================================

            df = pd.DataFrame(
                {
                    "Day": [
                        f"Day {i + 1}"
                        for i in range(len(predictions))
                    ],
                    "Predicted Sales": predictions,
                    "Promotion Count": onpromotion[
                        :len(predictions)
                    ],
                    "Holiday": [
                        "Yes" if h else "No"
                        for h in is_holiday[
                            :len(predictions)
                        ]
                    ]
                }
            )

            # ==================================================
            # BAR CHART
            # ==================================================

            st.subheader("📊 Predicted sales by day")

            st.bar_chart(
                df.set_index("Day")[
                    "Predicted Sales"
                ]
            )

            # ==================================================
            # LINE CHART
            # ==================================================

            st.subheader(
                "📈 Sales trend across the forecast window"
            )

            st.line_chart(
                df.set_index("Day")[
                    "Predicted Sales"
                ]
            )

            # ==================================================
            # RESULTS TABLE
            # ==================================================

            st.subheader("📋 Forecast Details")

            st.dataframe(
                df,
                use_container_width=True
            )

            # ==================================================
            # QUICK ANALYSIS
            # ==================================================

            st.subheader("🔍 Quick Analysis")

            avg_sales = df["Predicted Sales"].mean()
            max_sales = df["Predicted Sales"].max()
            min_sales = df["Predicted Sales"].min()

            metric1, metric2, metric3 = st.columns(3)

            metric1.metric(
                "Average Predicted Sales",
                f"{avg_sales:,.2f}"
            )

            metric2.metric(
                "Highest Predicted Sales",
                f"{max_sales:,.2f}"
            )

            metric3.metric(
                "Lowest Predicted Sales",
                f"{min_sales:,.2f}"
            )

            # Promotion analysis
            promo_mask = df["Promotion Count"] > 0

            if promo_mask.any():

                promo_average = df.loc[
                    promo_mask,
                    "Predicted Sales"
                ].mean()

                st.write(
                    f"Average predicted sales on promotion days: "
                    f"**{promo_average:,.2f}**"
                )

            if (~promo_mask).any():

                nonpromo_average = df.loc[
                    ~promo_mask,
                    "Predicted Sales"
                ].mean()

                st.write(
                    f"Average predicted sales on non-promotion days: "
                    f"**{nonpromo_average:,.2f}**"
                )

            # ==================================================
            # SAVE FORECAST TO POSTGRESQL
            # ==================================================

            try:

                if db_ready:

                    state.save_forecast(
                        store_nbr=store_nbr,
                        family=family,
                        horizon=horizon,
                        onpromotion=onpromotion,
                        is_holiday=is_holiday,
                        predictions=predictions
                    )

                    st.caption(
                        "Forecast saved to PostgreSQL."
                    )

                else:

                    st.warning(
                        "Forecast worked, but the database is "
                        f"unavailable: {db_startup_error}"
                    )

            except Exception as db_error:

                st.warning(
                    "Forecast worked, but history "
                    f"could not be saved: {db_error}"
                )

        except requests.exceptions.RequestException as api_error:

            st.error(
                "Could not connect to the forecasting API."
            )

            st.error(
                f"API error: {api_error}"
            )

        except Exception as error:

            st.error(
                f"Forecast failed: {error}"
            )


# ============================================================
# FILE UPLOAD (Azure Blob Storage via managed identity)
# ============================================================

st.divider()

st.header("📁 Upload a File")

st.caption(
    "Files are stored in Azure Blob Storage, not on the container's disk."
)

uploaded = st.file_uploader("Choose a file to upload")

if uploaded is not None and st.button("Upload to storage"):

    try:

        blob_name = state.upload_file(
            uploaded.name,
            uploaded.getvalue()
        )

        st.success(f"Uploaded to Blob Storage as: {blob_name}")

    except Exception as upload_error:

        st.error(f"Upload failed: {upload_error}")


# ============================================================
# FORECAST HISTORY
# ============================================================

st.divider()

st.header("🗄️ Forecast History")

try:

    if db_ready:

        row_count = state.count_rows("forecast_history")

        st.metric("Rows in forecast_history", row_count)

        records = state.load_history(20)

        if records:

            history_df = pd.DataFrame(records)

            st.dataframe(
                history_df,
                use_container_width=True
            )

        else:

            st.info(
                "No forecasts have been stored yet."
            )

    else:

        st.info(
            "Database history is currently unavailable."
        )

except Exception as history_error:

    st.warning(
        f"Could not load history: {history_error}"
    )
