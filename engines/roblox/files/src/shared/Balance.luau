--- 밸런스 수치의 유일한 자리. GDD 부록 A.1 과 1:1 로 대응한다 — 각 줄의 `-- GDD:` 표식이 그 짝이다.
---
--- 값은 밸런스 표(data/balance.xlsx)에서 고친다. Studio 플레이 테스트는 표를 내주는 서버(balance_table.py serve)에서
--- 값을 가져와 아래 값을 덮는다 (BalanceWatch.server.luau). 아래 적힌 숫자는 구운 값이다: 올린 게임은 이 값만 쓴다.
--- 쓰는 쪽은 쓸 때마다 `Balance.NAME` 으로 읽는다 — `local x = Balance.NAME` 으로 받아 두면 옛 값을 쥐고 있게 된다.
---
--- 놓는 자리: ReplicatedStorage.Shared.Balance (서버와 클라이언트가 같이 쓴다).

local RunService = game:GetService("RunService")

local Balance = {}

--- 예시 값이다 — 게임에 맞게 바꾼다. 한 줄에 숫자 하나, 줄 끝에 표식.
Balance.PLAYER_HP = 100 -- GDD: BAL.PLAYER.HP
--- 걷는 속도 (스터드/초)
Balance.PLAYER_WALK_SPEED = 16.0 -- GDD: BAL.PLAYER.WALK_SPEED
Balance.COIN_VALUE = 5 -- GDD: BAL.COIN.VALUE

-- ── 밸런스 표 ────────────────────────────────────────────────────────────────
-- 값은 위에만 적는다. 아래는 실행 중에 값을 덮는 장치다.

local changed = Instance.new("BindableEvent")

--- 값이 바뀌면 (이름, 전, 후) 로 알린다. 받아 둔 값을 고쳐야 하는 쪽이 듣는다.
Balance.Changed = changed.Event

local function set(name, value)
	local was = Balance[name]
	if type(was) ~= "number" or type(value) ~= "number" or was == value then
		return false
	end
	Balance[name] = value
	changed:Fire(name, was, value)
	return true
end

--- {이름 = 숫자} 로 값을 덮는다. 바뀐 것을 {이름 = {전, 후}} 로 돌려준다. 서버에서만 부른다.
--- 바뀐 값은 이 모듈의 속성(Attribute)으로도 적는다 — 속성은 클라이언트로 복제되므로 클라이언트 쪽 값도 따라 바뀐다.
function Balance.apply(rows)
	local out = {}
	for name, value in pairs(rows) do
		local was = Balance[name]
		if set(name, value) then
			out[name] = { was, value }
			script:SetAttribute(name, value)
		end
	end
	return out
end

if RunService:IsClient() then
	-- 늦게 들어온 클라이언트도 서버가 이미 덮어 둔 값을 받는다
	for name, value in pairs(script:GetAttributes()) do
		set(name, value)
	end
	script.AttributeChanged:Connect(function(name)
		set(name, script:GetAttribute(name))
	end)
end

return Balance
