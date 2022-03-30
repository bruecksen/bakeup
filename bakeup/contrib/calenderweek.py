import datetime

class CalendarWeek:
    """
    An interval of 7 days identified by their
    ISO-8601 calendar week and year.
    """
    ...

    def __init__(self, week: int, year: int):
        self.week = week
        self.year = year

    def __iter__(self):
        """Iterates all days in a calendar week"""
        for day in range(1, 8):
            yield datetime.date.fromisocalendar(self.year, self.week, day)

    def _last_calendarweek_ofyear(self, year):
        return datetime.date(year, 12, 28).isocalendar()[1]

    def next(self):
        last = self._last_calendarweek_ofyear(self.year)
        if self.week == last:
            return CalendarWeek(week=1, year=self.year + 1)
        return CalendarWeek(week=self.week + 1, year=self.year)

    def last(self):
        if self.week == 1:
            last_year = self.year - 1
            lastweek = self._last_calendarweek_ofyear(last_year)
            return CalendarWeek(week=lastweek, year=last_year)
        return CalendarWeek(week=self.week - 1, year=self.year)