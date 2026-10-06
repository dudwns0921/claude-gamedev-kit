--- 밸런스 런타임(Balance · BalanceWatch)을 Studio 없이 돌려 본다 — Roblox 쪽은 흉내로 채운다.
--- 실행: lune run tests/balance_runtime.luau <serve 주소>
local fs = require("@lune/fs")
local luau = require("@lune/luau")
local net = require("@lune/net")
local process = require("@lune/process")
local serde = require("@lune/serde")

local url = process.args[1]
local fails = 0
local function check(name, ok, detail)
	print((ok and "  ok   " or "  FAIL ") .. name .. ((ok or not detail) and "" or "  [" .. tostring(detail) .. "]"))
	if not ok then
		fails += 1
	end
end

local function signal()
	local handlers = {}
	local event = {}
	function event:Connect(fn)
		table.insert(handlers, fn)
	end
	return event, function(...)
		for _, fn in ipairs(handlers) do
			fn(...)
		end
	end
end

-- 서버와 클라이언트가 같이 보는 모듈 인스턴스 (속성이 복제되는 자리)
local attributes = {}
local attrChanged, fireAttr = signal()
local moduleScript = { AttributeChanged = attrChanged }
function moduleScript:SetAttribute(name, value)
	attributes[name] = value
	fireAttr(name)
end
function moduleScript:GetAttribute(name)
	return attributes[name]
end
function moduleScript:GetAttributes()
	return table.clone(attributes)
end

local function loadBalance(isClient)
	local env = {
		script = moduleScript,
		Instance = {
			new = function()
				local event, fire = signal()
				return {
					Event = event,
					Fire = function(_, ...)
						fire(...)
					end,
				}
			end,
		},
		game = {
			GetService = function(_, _name)
				return {
					IsClient = function()
						return isClient
					end,
				}
			end,
		},
	}
	return luau.load(fs.readFile("src/shared/Balance.luau"), { debugName = "Balance", environment = env })()
end

local server = loadBalance(false)
check("구운 값으로 뜬다", server.PLAYER_HP == 100 and server.PLAYER_WALK_SPEED == 16)

local heard = {}
server.Changed:Connect(function(name, was, now)
	heard[name] = { was, now }
end)

-- BalanceWatch 를 두 바퀴만 돌린다
local rounds = 0
local STOP = "stop"
local watchEnv = {
	game = {
		GetService = function(_, name)
			if name == "HttpService" then
				return {
					GetAsync = function(_, target)
						local res = net.request(target or url)
						if not res.ok then
							error("HTTP " .. res.statusCode)
						end
						return res.body
					end,
					JSONDecode = function(_, text)
						return serde.decode("json", text)
					end,
				}
			elseif name == "RunService" then
				return {
					IsStudio = function()
						return true
					end,
				}
			end
			local shared = {
				WaitForChild = function()
					return "balance-module"
				end,
			}
			return {
				WaitForChild = function()
					return shared
				end,
			}
		end,
	},
	require = function()
		return server
	end,
	task = {
		wait = function()
			rounds += 1
			if rounds >= 2 then
				error(STOP)
			end
		end,
	},
	print = print,
	warn = print,
}
local source = fs.readFile("src/server/BalanceWatch.server.luau")
check("주소가 틀과 같다", string.find(source, url, 1, true) ~= nil, url)
local ok, err = pcall(luau.load(source, { debugName = "BalanceWatch", environment = watchEnv }))
check("감시가 돌다가 멈춘다", not ok and string.find(tostring(err), STOP, 1, true) ~= nil, err)
check("표의 값으로 덮는다", server.PLAYER_HP == 130 and server.PLAYER_WALK_SPEED == 12.5, server.PLAYER_HP)
check(
	"바뀐 것만 알린다",
	heard.PLAYER_HP and heard.PLAYER_HP[1] == 100 and heard.PLAYER_HP[2] == 130 and heard.COIN_VALUE == nil
)
check("모르는 이름은 넘긴다", server.NO_SUCH_NAME == nil)
check("속성으로 적는다", attributes.PLAYER_HP == 130)

-- 늦게 들어온 클라이언트
local client = loadBalance(true)
check(
	"클라이언트가 덮인 값을 받는다",
	client.PLAYER_HP == 130 and client.PLAYER_WALK_SPEED == 12.5,
	client.PLAYER_HP
)
server.apply({ COIN_VALUE = 9 })
check("뒤에 바뀐 값도 따라온다", client.COIN_VALUE == 9, client.COIN_VALUE)

print(fails == 0 and "SMOKE OK" or ("SMOKE FAIL: " .. fails))
process.exit(fails == 0 and 0 or 1)
