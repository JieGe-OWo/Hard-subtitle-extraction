/** SRT 时间码与秒数互转（校对页用） */

const TIME_RE = /^(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})$/

/** 'HH:MM:SS,mmm' -> 毫秒 */
export function timeToMs(t) {
  const m = TIME_RE.exec(String(t).trim())
  if (!m) return 0
  const ms = Number(m[4].padEnd(3, '0'))
  return Number(m[1]) * 3600000 + Number(m[2]) * 60000 + Number(m[3]) * 1000 + ms
}

/** 毫秒 -> 'HH:MM:SS,mmm' */
export function msToTime(ms) {
  const total = Math.max(0, Math.round(ms))
  const h = Math.floor(total / 3600000)
  const m = Math.floor((total % 3600000) / 60000)
  const s = Math.floor((total % 60000) / 1000)
  const milli = total % 1000
  const pad = n => String(n).padStart(2, '0')
  return `${pad(h)}:${pad(m)}:${pad(s)},${String(milli).padStart(3, '0')}`
}

/** 'HH:MM:SS,mmm' -> 秒（小数），给 video.currentTime 用 */
export function timeToSec(t) {
  return timeToMs(t) / 1000
}
