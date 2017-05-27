-------------------------------------------------
--
-- MCMultipartMime.lua
-- Original Author: Brill Pappin, Sixgreen Labs Inc.
--
-- Enhancements Copyright 2014-2015 Keith Kyzivat
-- Enhancements: Support for multipart/mixed and multipart/related
-- NOTE: multipart/form-data does not work in LR due to dependence on ltn12/coroutines
--
-- Generates multipart data for http POST/PUT calls that require it.
--
-- Caution:
-- In Corona SDK you have to set a string as the body, which means that the
-- entire POST needs to be encoded as a string, including any files you attach.
-- Needless to say, if the file you are sending is large, it''s going to use
-- up all your available memory!
--
-- Example:
--[[
require "MCMultipartMime"

local multipart = mc.MultipartMime.new()
multipart:addHeader("Customer-Header", "Custom Header Value")
multipart:addField("myFieldName","myFieldValue")
multipart:addField("banana","yellow")
multipart:addFile("myfile", system.pathForFile( "myfile.jpg", system.DocumentsDirectory ), "image/jpeg", "myfile.jpg")

local params = {}
params.body = multipart:getBody() -- Must call getBody() first!
params.headers = multipart:getHeaders() -- Headers not valid until getBody() is called.

local function networkListener( event )
    if ( event.isError ) then
        print( "Network error!")
    else
        print ( "RESPONSE: " .. event.response )
    end
end

network.request( "http://www.example.com", "POST", networkListener, params)

]]

-- Imports
local LrStringUtils = import "LrStringUtils"

require "MCUuid"

-------------------------------------------------
--require "ltn12" -- ltn12 source/sink pump doesn't work in LR due to use of coroutines

MULTIPART_TYPE_FORMDATA='multipart/form-data'
MULTIPART_TYPE_MIXED='multipart/mixed'
MULTIPART_TYPE_RELATED='multipart/related'

mc.MultipartMime = {}
local MultipartMime_mt = { __index = mc.MultipartMime }

local function mimeNormalizeEol(ctx, input, marker)
    marker = marker or "\r\n"

    local outTable = {}
    local eolProcess = function(c, last)
        if c == '\r' or c == '\n' then
            if last == '\r' or last == '\n' then
                if c == last then
                    table.insert(outTable, marker)
                    return nil
                end
            else
                table.insert(outTable, marker)
                return c
            end
        else
            table.insert(outTable, c)
            return nil
        end
    end

    if not input then
        return nil, 0
    end

    local curIdx = 1
    while curIdx <= #input do
        ctx = eolProcess(input:sub(curIdx, curIdx), ctx, marker)
        curIdx = curIdx + 1
    end

    return table.concat(outTable), ctx
end

local function mimeNormalize(marker)
    return filter.cycle(mimeNormalizeEol, nil, marker)
end

local function encodeBase64Filter()
    local encodeBase64 = function(ctx, chunk, extra)
        return LrStringUtils.encodeBase64(chunk), nil
    end
    return filter.cycle(encodeBase64, nil, nil)
end

function mc.MultipartMime.new()  -- The constructor
    local newBoundary = mc.generateUUID()
    local object = {
    isClass = true,
    boundary = newBoundary,
    type=MULTIPART_TYPE_FORMDATA,
    headers = {},
    elements = {},
    }

    object.headers["Content-Type"] = ""
    object.headers["Content-Length"] = ""
    object.headers["Accept"] = "*/*"
    object.headers["Accept-Encoding"] = "gzip"
    object.headers["Accept-Language"] = "en-us"
    object.headers["connection"] = "keep-alive"
    return setmetatable( object, MultipartMime_mt )
end

function mc.MultipartMime:setType(type)
    if not (type == MULTIPART_TYPE_FORMDATA or
            type == MULTIPART_TYPE_MIXED or
            type == MULTIPART_TYPE_RELATED) then
        error(string.format("Cannot handle multipart mime type %s", type))
    end
    self.type = type
end

function mc.MultipartMime:getBody()
    local src = {}

    -- always need two CRLF's as the beginning
    --table.insert(src, source.chain(source.string("\n"), mimeNormalize()))

    for i = 1, #self.elements do
        local el = self.elements[i]
        if el then
            if el.intent == "data" then
                local elData = {
                    "--"..self.boundary.."\r\n",
                    el.value,
                    --"\r\n"
                }
                table.insert(src, table.concat(elData))
            elseif el.intent == "field" then
                if self.type ~= MULTIPART_TYPE_FORMDATA then
                    error(string.format("Multipart type is %s, but found a field specifier specific to %s", self.type, MULTIPART_TYPE_FORMDATA))
                end
                local elData = {
                    "--"..self.boundary.."\r\n",
                    "content-disposition: form-data; name=\"",
                    el.name,
                    "\"\r\n\r\n",
                    el.value,
                    --"\r\n"
                }

                local elBody = table.concat(elData)
                table.insert(src, source.chain(source.string(elBody), mimeNormalize()))
            elseif el.intent == "file" then
                local elData = {
                    "--"..self.boundary.."\r\n",
                    "content-disposition: form-data; name=\"",
                    el.name,
                    "\"; filename=\"",
                    el.filename,
                    "\"\r\n",
                    "Content-Type: ",
                    el.mimetype,
                    "\r\n\r\n",
                }
                local elHeader = table.concat(elData)

                local elFile = io.open( el.path, "rb" )
                assert(elFile)
                local fileSource = source.cat(
                            source.chain(source.string(elHeader), mimeNormalize()),
                            source.chain(
                                    source.file(elFile),
                                    encodeBase64Filter()
                                    --filter.chain(
                                    --    encodeBase64Filter()
                                    --    mime.wrap() -- Not implemented in pure lua yet
                                    --)
                                )
                        )

                table.insert(src, fileSource)
            end
        end
    end

    -- always need to end the body
    table.insert(src, "\r\n--"..self.boundary.."--")
    --table.insert(src, source.chain(source.string("\r\n--"..self.boundary.."--"), mimeNormalize()))

    local body = table.concat(src)
    --local so = source.empty()
    --for i = 1, #src do
    --    so = source.cat(so, src[i])
    --end
    --
    --local si, data = sink.table()
    --pump.all(so,si)
    --local body = table.concat(data)

    -- update the headers we now know how to add based on the multipart data we just generated.
    self.headers["Content-Type"] = self.type.."; boundary="..self.boundary
    self.headers["Content-Length"] = string.len(body) -- must be total length of body

    return body
end

function mc.MultipartMime:getCoronaHeaders()
    assert(self.headers["Content-Type"])
    assert(self.headers["Content-Length"])
    return self.headers
end

function mc.MultipartMime:getHeaders()
    local lrHeaders = {}
    for k,v in pairs(self:getCoronaHeaders()) do
        table.insert(lrHeaders, { field=k, value=v })
    end

    return lrHeaders
end

function mc.MultipartMime:addHeader(name, value)
    self.headers[name] = value
end

function mc.MultipartMime:setBoundry(string)
    self.boundary = string
end

function mc.MultipartMime:addField(name, value)
    error("mc.MultipartMime:addField(name, value) not supported in LR")
    self:add("field", name, value)
end

function mc.MultipartMime:addFile(name, path, mimeType, remoteFileName)
    error("mc.MultipartMime:addFile not supported in LR")
    -- For Corona, we can really only use base64 as a simple binary
    -- won't work with their network.request method.
    local element = {intent="file", name=name, path=path,
        mimetype = mimeType, filename = remoteFileName}
    self:addElement(element)
end

function mc.MultipartMime:addData(value)
    self:add("data", nil, value)
end

function mc.MultipartMime:add(intent, name, value)
    local element = {intent=intent, name=name, value=value}
    self:addElement(element)
end

function mc.MultipartMime:addElement(element)
    table.insert(self.elements, element)
end

function mc.MultipartMime:toString()
    return "mc.MultipartMime [elementCount:"..tostring(#self.elements)..", headerCount:"..tostring(#self.headers).."]"
end

return mc.MultipartMime
