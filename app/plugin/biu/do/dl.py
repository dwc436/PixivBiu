# coding=utf-8
import json
import os
import re

from ....platform import CMDProcessor


@CMDProcessor.plugin_register("api/biu/do/dl")
class doDownload(object):
    def __init__(self, MOD):
        self.MOD = MOD
        self.code = 1

    def pRun(self, cmd):
        try:
            args = self.MOD.args.getArgs("dl", ["kt", "workID=0", "data=0"])
        except:
            return {"code": 0, "msg": "missing parameters"}

        if args["fun"]["workID"] == 0 and args["fun"]["data"] == 0:
            return {"code": 0, "msg": "missing parameters"}

        return {
            "code": self.code,
            "msg": {
                "way": "do",
                "args": args,
                "rst": self.dl(args["ops"].copy(), args["fun"].copy()),
            },
        }

    def dl(self, opsArg, funArg):
        if funArg["data"] == 0:
            r = self.MOD.biu.apiAssist.illust_detail(funArg["workID"])
            if "illust" not in r:
                self.code = 0
                return "error"
            r = r["illust"]
        else:
            r = json.loads(funArg["data"])

        if r["type"] != "illust" and r["type"] != "manga" and r["type"] != "ugoira":
            self.code = 0
            return "only support illustration, manga and ugoira"

        isSingle = len(r["meta_pages"]) is 0
        rootURI = (
            self.MOD.biu.sets["biu"]["download"]["saveURI"]
                .replace("{ROOTPATH}", self.MOD.ENVIRON["ROOTPATH"])
                .replace("{KT}", self.__pureName(funArg["kt"]))
        )

        if rootURI[-1] != "/":
            rootURI = rootURI + "/"

        rootURI = self.__deName(rootURI, r)
        picTitle = self.__pureName(
            self.__deName(self.MOD.biu.sets["biu"]["download"]["saveFileName"], r)
        )

        status = []

        if r["type"] != "ugoira" and isSingle:
            # 单图下载
            url = r["meta_single_page"]["original_image_url"].replace(
                "https://i.pximg.net", self.MOD.biu.pximgURL
            )
            status.append(
                self.getTemp(url, rootURI, picTitle + "." + r["meta_single_page"]["original_image_url"].split(".")[-1]))
        elif r["type"] != "ugoira" and not isSingle:
            # 多图下载
            index = 0
            # 判断是否自动归档
            if self.MOD.biu.sets["biu"]["download"]["autoArchive"]:
                ext = picTitle + "/"
            else:
                ext = ""
            for x in r["meta_pages"]:
                picURL = x["image_urls"]["original"]
                url = picURL.replace("https://i.pximg.net", self.MOD.biu.pximgURL)
                status.append(
                    self.getTemp(url, rootURI + ext, picTitle + "_" + str(index) + "." + picURL.split(".")[-1])
                )
                index = index + 1
        else:
            # 动图下载
            zipUrl, r_ = self.__getdlUgoiraPicsUrl(r["id"])
            temp = self.getTemp(zipUrl, rootURI + picTitle, "ugoira.zip", self.__callback_merge)
            temp["dlArgs"]["@ugoira"] = {
                "r": r_,
                "name": picTitle
            }
            status.append(temp)

        if self.MOD.dl.add(str(r["id"]), status):
            return "running"
        else:
            return False

    def getTemp(self, url, path, name, fun=None):
        return {
            "url": url,
            "folder": path,
            "name": name,
            "dlArgs": {
                "_headers": {
                    "referer": "https://app-api.pixiv.net/"
                },
                "@requests": {
                    "proxies": {"https": self.MOD.biu.proxy}
                },
                "@aria2": {
                    "referer": "https://app-api.pixiv.net/",
                    "all-proxy": self.MOD.biu.proxy
                }
            },
            "callback": fun
        }

    def __deName(self, name, data):
        return (
            name.replace("{title}", self.__pureName(str(data["title"])))
                .replace("{work_id}", self.__pureName(str(data["id"])))
                .replace("{user_name}", self.__pureName(str(data["user"]["name"])))
                .replace("{user_id}", self.__pureName(str(data["user"]["id"])))
                .replace("{type}", self.__pureName(str(data["type"])))
        )

    def __pureName(self, name):
        return re.sub(r'[/\\:*?"<>|]', "_", name)

    def __getdlUgoiraPicsUrl(self, id_):
        try:
            r = self.MOD.biu.apiAssist.ugoira_metadata(id_)
            r = r["ugoira_metadata"]
        except:
            return False
        url = (
            r["zip_urls"]["medium"]
                .replace("600x600", "1920x1080")
                .replace("https://i.pximg.net", self.MOD.biu.pximgURL)
        )
        return url, r

    def __callback_merge(self, this):
        if this.status(self.MOD.dl.mod.CODE_GOOD_SUCCESS):
            if self.MOD.dl.modName == "aria2" and self.MOD.dl.mod.HOST not in ("127.0.0.1", "localhost"):
                return False
            j = this._dlArgs["@ugoira"]["r"]["frames"]
            pl = []
            dl = []
            for x in j:
                pl.append(os.path.join(this._dlSaveDir, "./data", x["file"]))
                dl.append(x["delay"])
            try:
                self.MOD.file.unzip(os.path.join(this._dlSaveDir, "./data"), os.path.join(this._dlSaveDir, "ugoira.zip"))
                self.MOD.file.rm(os.path.join(this._dlSaveDir, "ugoira.zip"))
                if self.MOD.biu.sets["biu"]["download"]["whatsUgoira"] == "gif":
                    self.MOD.file.cov2gif(os.path.join(this._dlSaveDir, this._dlArgs["@ugoira"]["name"] + ".gif"), pl, dl)
                else:
                    self.MOD.file.cov2webp(os.path.join(this._dlSaveDir, this._dlArgs["@ugoira"]["name"] + ".webp"), pl, dl)
            except:
                return False
            return True