
tailwind.config = { theme: { extend: { fontFamily: { sans: ['Inter', 'sans-serif'], serif: ['Cinzel', 'serif'] }, colors: { shadow: { 900: '#0a0a0f', 800: '#14141d', 700: '#1e1e2b', blue: '#3b82f6', gold: '#fbbf24' } } } } };

function g2j(gy, gm, gd) {
    var g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    var gy2 = (gm > 2) ? (gy + 1) : gy;
    var days = 355666 + (365 * gy) + ~~( (gy2 + 3) / 4 ) - ~~( (gy2 + 99) / 100 ) + ~~( (gy2 + 399) / 400 ) + gd + g_d_m[gm - 1];
    var jy = -1595 + (33 * ~~(days / 12053));
    days %= 12053; jy += 4 * ~~(days / 1461); days %= 1461;
    if (days > 365) { jy += ~~((days - 1) / 365); days = (days - 1) % 365; }
    var jm = (days < 186) ? 1 + ~~(days / 31) : 7 + ~~((days - 186) / 30);
    var jd = 1 + ((days < 186) ? (days % 31) : ((days - 186) % 30));
    return [jy, jm, jd];
}
const jalaliMonths = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"];
const toFarsi = (num) => num.toString().replace(/\d/g, x => '۰۱۲۳۴۵۶۷۸۹'[x]);
