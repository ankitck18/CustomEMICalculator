import datetime as dt
import calendar as cal
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_EVEN, getcontext

# High precision for finance
getcontext().prec = 28


def finance_round(value, ndigits=2):
    """Banker's rounding (ROUND_HALF_EVEN)."""
    return Decimal(value).quantize(Decimal(10) ** -ndigits, rounding=ROUND_HALF_EVEN)


class DayCountConvention:
    """Day count conventions for year fraction."""

    @staticmethod
    def year_fraction_30_360(start_date, end_date):
        d1 = min(start_date.day, 30)
        d2 = min(end_date.day, 30)
        days = (end_date.year - start_date.year) * 360 + \
               (end_date.month - start_date.month) * 30 + (d2 - d1)
        return Decimal(days) / Decimal(360), days

    @staticmethod
    def year_fraction_actual_360(start_date, end_date):
        days = (end_date - start_date).days
        return Decimal(days) / Decimal(360), days

    @staticmethod
    def year_fraction_actual_365(start_date, end_date):
        days = (end_date - start_date).days
        return Decimal(days) / Decimal(365), days

    @staticmethod
    def year_fraction_actual_actual(start_date, end_date):
        days = (end_date - start_date).days
        year_days = 366 if cal.isleap(start_date.year) else 365
        return Decimal(days) / Decimal(year_days), days


class EMI_Calculator:
    """EMI calculator using PV formula with selectable DCC."""

    def __init__(self, principal, annual_rate, start_date, years,
                 convention="Actual/365", frequency="M"):
        self.P = Decimal(principal)
        self.R = Decimal(annual_rate) / 100
        self.start_date = start_date
        self.years = years
        self.convention = convention
        self.frequency = frequency

        self.periods_per_year = {"W": 52, "BW": 26, "M": 12,
                                 "Q": 4, "S": 2, "A": 1}[frequency]
        self.terms = self.years * self.periods_per_year

        # Select convention
        self.dcc = {
            "30/360": DayCountConvention.year_fraction_30_360,
            "Actual/360": DayCountConvention.year_fraction_actual_360,
            "Actual/365": DayCountConvention.year_fraction_actual_365,
            "Actual/Actual": DayCountConvention.year_fraction_actual_actual
        }[convention]

        self.emi = self.calculate_emi()

    def _adjust_end_of_month(self, date, months_to_add=1):
        """Maintain end-of-month when rolling dates."""
        new_date = date + relativedelta(months=months_to_add)
        last_day = cal.monthrange(new_date.year, new_date.month)[1]
        if date.day == cal.monthrange(date.year, date.month)[1]:
            return dt.date(new_date.year, new_date.month, last_day)
        return new_date

    def _generate_payment_dates(self):
        """Generate payment dates for the entire term."""
        dates = [self.start_date]
        d = self.start_date
        for _ in range(self.terms):
            if self.frequency == "W":
                d = d + relativedelta(weeks=1)
            elif self.frequency == "BW":
                d = d + relativedelta(weeks=2)
            elif self.frequency == "M":
                d = self._adjust_end_of_month(d, 1)
            elif self.frequency == "Q":
                d = self._adjust_end_of_month(d, 3)
            elif self.frequency == "S":
                d = self._adjust_end_of_month(d, 6)
            elif self.frequency == "A":
                d = self._adjust_end_of_month(d, 12)
            dates.append(d)
        return dates

    def calculate_emi(self):
        """Calculate EMI using PV summation (doc formula with DCC)."""
        dates = self._generate_payment_dates()
        prev_date = self.start_date
        F = Decimal("0")
        product = Decimal("1")

        for pay_date in dates[1:]:
            yf, _ = self.dcc(prev_date, pay_date)
            factor = (Decimal(1) + self.R * yf)
            product *= factor
            F += Decimal(1) / product
            prev_date = pay_date

        emi = self.P / F
        return finance_round(emi, 2)

    def get_schedule(self):
        """Generate amortization schedule."""
        schedule = []
        balance = self.P
        dates = self._generate_payment_dates()
        prev_date = self.start_date

        for i, pay_date in enumerate(dates[1:], start=1):
            yf, days = self.dcc(prev_date, pay_date)
            interest = finance_round(balance * self.R * yf, 2)
            principal = self.emi - interest
            balance -= principal

            if i == self.terms:  # last adjustment
                principal += balance
                emi = principal + interest
                balance = Decimal("0.00")
            else:
                emi = self.emi

            schedule.append({
                "Payment #": i,
                "Payment Date": pay_date.strftime("%Y-%m-%d"),
                "Opening Balance": finance_round(balance + principal, 2),
                "Principal": finance_round(principal, 2),
                "Interest": finance_round(interest, 2),
                "EMI": finance_round(emi, 2),
                "Closing Balance": finance_round(balance, 2)
            })
            prev_date = pay_date

        return schedule

    def print_schedule(self):
        """Print amortization schedule with totals."""
        schedule = self.get_schedule()
        total_principal = sum(r["Principal"] for r in schedule)
        total_interest = sum(r["Interest"] for r in schedule)

        print(f"{'Pmt#':<5} {'Date':<12} {'Opening':<12} {'Principal':<10} {'Interest':<10} {'EMI':<10} {'Closing':<12}")
        for row in schedule:
            print(f"{row['Payment #']:<5} {row['Payment Date']:<12} "
                  f"{row['Opening Balance']:<12} {row['Principal']:<10} "
                  f"{row['Interest']:<10} {row['EMI']:<10} {row['Closing Balance']:<12}")

        print("\nSummary:")
        print(f"  Total Payments : {finance_round(total_principal + total_interest, 2)}")
        print(f"  Total Principal: {finance_round(total_principal, 2)}")
        print(f"  Total Interest : {finance_round(total_interest, 2)}")


# Example usage with user input
if __name__ == "__main__":
    principal = Decimal(input("Enter loan principal: ") or "10000")
    annual_rate = Decimal(input("Enter annual rate (%): ") or "9")
    years = int(input("Enter term in years: ") or "2")
    start_date = dt.datetime.strptime(input("Enter start date (YYYY-MM-DD): ") or "2024-01-31", "%Y-%m-%d").date()
    frequency = input("Enter frequency (W, BW, M, Q, S, A): ") or "M"
    convention = input("Enter day count convention (30/360, Actual/360, Actual/365, Actual/Actual): ") or "Actual/365"

    calc = EMI_Calculator(
        principal=principal,
        annual_rate=annual_rate,
        start_date=start_date,
        years=years,
        convention=convention,
        frequency=frequency
    )
    print("\nEMI =", calc.emi)
    calc.print_schedule()
