local function trim(s)
  if s == nil then return "" end
  return (s:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function read_config(path)
  local cfg = {}
  local file = io.open(path, "r")
  if not file then
    return cfg
  end
  for line in file:lines() do
    local key, value = string.match(line, "^([A-Z_]+)=(.*)$")
    if key ~= nil and value ~= nil then
      cfg[key] = trim(value)
    end
  end
  file:close()
  return cfg
end

local function bcd_to_dec(byte_val)
  local hi = math.floor(byte_val / 16)
  local lo = byte_val % 16
  return (hi * 10) + lo
end

local function read_duck_hunt_score()
  local b1 = memory.readbyte(0x00C4)
  local b2 = memory.readbyte(0x00C5)
  local b3 = memory.readbyte(0x00C6)
  if b1 == nil or b2 == nil or b3 == nil then
    return 0
  end
  return (bcd_to_dec(b1) * 10000) + (bcd_to_dec(b2) * 100) + bcd_to_dec(b3)
end

local cfg_path = os.getenv("LIGHTGUN_SCORE_CFG")
if cfg_path == nil or cfg_path == "" then
  cfg_path = "./data/cache/score_capture.conf"
end

local cfg = read_config(cfg_path)
local game = string.lower(cfg["GAME"] or "")
local outfile = cfg["OUTFILE"] or "./data/cache/last_score.json"
local start_ts = tonumber(cfg["START_TS"] or "0") or 0

local best = 0
local last_write_frame = -999999

local function write_score(score)
  local f = io.open(outfile, "w")
  if not f then
    return
  end
  local ts = os.time()
  local payload = string.format(
    "{\"game\":\"%s\",\"score\":%d,\"timestamp\":%d,\"start_ts\":%d}\n",
    game,
    score,
    ts,
    start_ts
  )
  f:write(payload)
  f:close()
end

while true do
  if game == "duck_hunt" or game == "duckhunt" then
    local score = read_duck_hunt_score()
    if score > best then
      best = score
    end
  end

  local frame = emu.framecount()
  if (frame - last_write_frame) >= 60 then
    write_score(best)
    last_write_frame = frame
  end
  emu.frameadvance()
end
