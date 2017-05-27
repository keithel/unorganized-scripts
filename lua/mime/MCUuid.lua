--[[
-- Copyright 2014-2015, Keith Kyzivat
--
-- Author: Keith Kyzivat <kkyzivat@on1.com>
--]]

-- Imports
local LrMath = import "LrMath"

-- Namespace
mc = mc or {}

--
-- Generates a unique id
-- Source reference: http://developer.coronalabs.com/code/uuidguid-string-generator-coronalua
--
function mc.generateUUID()
    local chars = {"0","1","2","3","4","5","6","7","8","9","A","B","C","D","E","F"}
    local uuid = {[9]="-",[14]="-",[15]="4",[19]="-",[24]="-"}

    local r, index

    for i = 1,36 do
        if (uuid[i]==nil) then
            r = math.random(16)

            if (i == 20) then
                -- (r & 0x3) | 0x8
                index = LrMath.bitOr(LrMath.bitAnd(r, 3), 8)
                if (index < 1 or index > 16) then
                    -- TODO: Use your choice of logging to log that this failed.
                    return mc.generateUUID() -- should never happen - try again if it does
                end
            else
                index = r
            end

            uuid[i] = chars[index]
        end
    end

    return table.concat(uuid)
end

