--- 밸런스 표를 지켜보다가 저장되면 다시 읽는다 — 플레이 테스트를 끄지 않고 값을 바꿔 본다.
---
--- Roblox 는 디스크의 엑셀을 읽지 못한다. 그래서 `balance_table.py serve` 가 이 컴퓨터에서 표를 JSON 으로 내주고,
--- 이 스크립트가 그것을 가져온다. Studio 에서만 돈다 — 올린 게임에서는 첫 줄에서 끝난다.
--- Game Settings → Security → Allow HTTP Requests 를 켜야 한다.
---
--- 놓는 자리: ServerScriptService. Balance 는 ReplicatedStorage.Shared.Balance 에 있다고 본다.

local HttpService = game:GetService("HttpService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

if not RunService:IsStudio() then
	return
end

local Balance = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Balance"))

local URL = "http://127.0.0.1:8765/balance"
local POLL_SEC = 0.5
local RETRY_SEC = 5

local stamp = ""
local warned = false

while true do
	local pause = POLL_SEC
	local ok, body = pcall(function()
		return HttpService:GetAsync(URL, true)
	end)
	if ok then
		warned = false
		local decoded, data = pcall(function()
			return HttpService:JSONDecode(body)
		end)
		if decoded and type(data) == "table" and type(data.values) == "table" and data.stamp ~= stamp then
			stamp = data.stamp
			for name, pair in pairs(Balance.apply(data.values)) do
				print(string.format("[balance] %s  %s → %s", name, tostring(pair[1]), tostring(pair[2])))
			end
		end
	elseif string.find(tostring(body), "503", 1, true) then
		-- 엑셀이 저장하는 도중이다 — 다음 번에 다시 읽는다
	else
		if not warned then
			warn("[balance] 표를 가져오지 못했다 — balance_table.py serve 가 켜져 있는가, HTTP 요청이 허용돼 있는가: " .. tostring(body))
			warned = true
		end
		pause = RETRY_SEC
	end
	task.wait(pause)
end
