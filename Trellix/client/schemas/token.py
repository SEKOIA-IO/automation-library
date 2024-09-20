"""All models related to auth token workflow."""

from enum import Enum
from time import time
from typing import List, Set

from pydantic import BaseModel


class HttpToken(BaseModel):
    """Http model for auth token response."""

    tid: int
    token_type: str
    expires_in: int
    access_token: str


class Scope(str, Enum):
    """
    Scope enum.

    Some of them can be found here:
    https://docs.trellix.com/fr/bundle/mvision-endpoint-detection-and-response-product-guide/page/GUID-A5D15066-C579-459F-9686-D79AF40E66D7.html
    """

    SOC_HTS_C = "soc.hts.c"
    SOC_HTS_R = "soc.hts.r"
    SOC_RTS_C = "soc.rts.c"
    SOC_RTS_R = "soc.rts.r"
    SOC_QRY_PR = "soc.qry.pr"
    SOC_CFG_W = "soc.cfg.w"
    SOC_CFG_R = "soc.cfg.r"
    SOC_ACT_TG = "soc.act.tg"
    SOC_EPY_W = "soc.epy.w"
    MI_USER_INVESTIGATE = "mi.user.investigate"
    API_CNF_R = "api.cnf.r"
    API_PR_R = "api.pr.r"
    DHUB_APP_R = "dhub.app.r"
    DHUB_APP_W = "dhub.app.w"
    DHUB_CMN_RES_R = "dhub.cmn.res.r"
    DHUB_SP_R = "dhub.sp.r"
    DHUB_SP_U = "dhub.sp.u"
    DHUB_W = "dhub.w"
    DHUB_XO_CUS_R = "dhub.xo.cus.r"
    DHUB_XO_ET_R = "dhub.xo.et.r"
    DHUB_XOT_SUB_R = "dhub.xot.sub.r"
    DP_IM_R = "dp.im.r"
    ENS_AM_A = "ens.am.a"
    ENS_AM_R = "ens.am.r"
    ENS_AM_TA = "ens.am.ta"
    ENS_AM_TR = "ens.am.tr"
    ENS_AM_VE = "ens.am.ve"
    ENS_AM_VS = "ens.am.vs"
    ENS_ATP_A = "ens.atp.a"
    ENS_ATP_R = "ens.atp.r"
    ENS_ATP_VS = "ens.atp.vs"
    ENS_COMN_A = "ens.comn.a"
    ENS_COMN_R = "ens.comn.r"
    ENS_COMN_TA = "ens.comn.ta"
    ENS_COMN_TR = "ens.comn.tr"
    ENS_COMN_VS = "ens.comn.vs"
    ENS_FW_A = "ens.fw.a"
    ENS_FW_R = "ens.fw.r"
    ENS_FW_VC = "ens.fw.vc"
    ENS_FW_VP = "ens.fw.vp"
    ENS_FW_VR = "ens.fw.vr"
    ENS_FW_VS = "ens.fw.vs"
    ENS_VRS_A = "ens.vrs.a"
    ENS_VRS_R = "ens.vrs.r"
    ENS_VRS_TA = "ens.vrs.ta"
    ENS_VRS_TR = "ens.vrs.tr"
    ENS_WP_A = "ens.wp.a"
    ENS_WP_R = "ens.wp.r"
    ENS_WP_TA = "ens.wp.ta"
    ENS_WP_TR = "ens.wp.tr"
    ENS_WP_VS = "ens.wp.vs"
    EPO_ADIT_A = "epo.adit.a"
    EPO_ADIT_R = "epo.adit.r"
    EPO_ADMIN = "epo.admin"
    EPO_AGNT_D = "epo.agnt.d"
    EPO_AGNT_W = "epo.agnt.w"
    EPO_CDS_R = "epo.cds.r"
    EPO_DASH_P = "epo.dash.p"
    EPO_DASH_R = "epo.dash.r"
    EPO_DIR_A = "epo.dir.a"
    EPO_DXLC_A = "epo.dxlc.a"
    EPO_DXLC_R = "epo.dxlc.r"
    EPO_EAGT_A = "epo.eagt.a"
    EPO_EAGT_R = "epo.eagt.r"
    EPO_EAGT_TA = "epo.eagt.ta"
    EPO_EAGT_TR = "epo.eagt.tr"
    EPO_EVT_R = "epo.evt.r"
    EPO_PEVT_R = "epo.pevt.r"
    EPO_PEVT_RP = "epo.pevt.rp"
    EPO_QERY_G = "epo.qery.g"
    EPO_QERY_U = "epo.qery.u"
    EPO_REG_TOKEN = "epo.reg_token"
    EPO_RESP_RA = "epo.resp.ra"
    EPO_RESP_RU = "epo.resp.ru"
    EPO_SDLR_E = "epo.sdlr.e"
    EPO_SDLR_R = "epo.sdlr.r"
    EPO_TAG_A = "epo.tag.a"
    EPO_TAGC_A = "epo.tagc.a"
    EPO_TAGC_U = "epo.tagc.u"
    EPO_TREE_M = "epo.tree.m"
    EPO_UBP_AE = "epo.ubp.ae"
    EPO_UBP_R = "epo.ubp.r"
    FRP_ACT_R = "frp.act.r"
    FRP_KEYS_R = "frp.keys.r"
    FRP_KEYS_X = "frp.keys.x"
    FRP_PO_R = "frp.po.r"
    FRP_PO_X = "frp.po.x"
    FRP_PROP_V = "frp.prop.v"
    INS_NOTI_R = "ins.noti.r"
    MI_USER_CONFIG = "mi.user.config"
    MNE_ACT_R = "mne.act.r"
    MNE_PO_A = "mne.po.a"
    MNE_PO_R = "mne.po.r"
    MNE_PROP_V = "mne.prop.v"
    MP_CMN_RES_R = "mp.cmn.res.r"
    MP_CUS_R = "mp.cus.r"
    MP_SUB_R = "mp.sub.r"
    MP_SUB_W = "mp.sub.w"
    MP_XO_APP_R = "mp.xo.app.r"
    MP_XO_ET_R = "mp.xo.et.r"
    MVS_ENDP_A = "mvs.endp.a"
    MVS_ENDP_R = "mvs.endp.r"
    NDLP_CPO_A = "ndlp.cpo.a"
    NDLP_CPO_R = "ndlp.cpo.r"
    NDLP_DASH_R = "ndlp.dash.r"
    NDLP_PO_A = "ndlp.po.a"
    NDLP_PO_R = "ndlp.po.r"
    TKS_CK_R = "tks.ck.r"
    TKS_CK_X = "tks.ck.x"
    UAM_CC_R = "uam.cc.r"
    UAM_CC_W = "uam.cc.w"
    UDLP_CL_F = "udlp.cl.f"
    UDLP_CL_M = "udlp.cl.m"
    UDLP_CL_RD = "udlp.cl.rd"
    UDLP_CL_U = "udlp.cl.u"
    UDLP_CL_V = "udlp.cl.v"
    UDLP_DFN_F = "udlp.dfn.f"
    UDLP_DFN_U = "udlp.dfn.u"
    UDLP_DFN_V = "udlp.dfn.v"
    UDLP_DIS_F = "udlp.dis.f"
    UDLP_DS_A = "udlp.ds.a"
    UDLP_DS_BR = "udlp.ds.br"
    UDLP_DS_G = "udlp.ds.g"
    UDLP_HD_AMRK = "udlp.hd.amrk"
    UDLP_HD_AOK = "udlp.hd.aok"
    UDLP_HD_ARQK = "udlp.hd.arqk"
    UDLP_HD_AUK = "udlp.hd.auk"
    UDLP_IM_VF = "udlp.im.vf"
    UDLP_IM_VM = "udlp.im.vm"
    UDLP_IMDRL_F = "udlp.imdrl.f"
    UDLP_IMDRS_F = "udlp.imdrs.f"
    UDLP_IMDUM_F = "udlp.imdum.f"
    UDLP_OE_F = "udlp.oe.f"
    UDLP_PC_V = "udlp.pc.v"
    UDLP_PM_F = "udlp.pm.f"
    UDLP_PM_TDSCVR = "udlp.pm.tdscvr"
    UDLP_PM_TDT = "udlp.pm.tdt"
    UDLP_PM_TDVC = "udlp.pm.tdvc"
    UDLP_PM_U = "udlp.pm.u"
    UDLP_PM_V = "udlp.pm.v"
    OPENID = "openid"
    MV_M_ADMIN = "mv:m:admin"

    @classmethod
    def threats_set_of_scopes(cls) -> Set["Scope"]:
        return {cls.SOC_ACT_TG}

    @classmethod
    def complete_set_of_scopes(cls) -> Set["Scope"]:
        """
        Get complete list of scopes to work with all Trellix api endpoints.

        Returns:
            set:
        """
        return {
            cls.SOC_HTS_C,
            cls.SOC_HTS_R,
            cls.SOC_RTS_C,
            cls.SOC_RTS_R,
            cls.SOC_QRY_PR,
            cls.SOC_CFG_W,
            cls.SOC_CFG_R,
            cls.SOC_ACT_TG,
            cls.SOC_EPY_W,
            cls.MI_USER_INVESTIGATE,
            cls.API_CNF_R,
            cls.API_PR_R,
            cls.DHUB_APP_R,
            cls.DHUB_APP_W,
            cls.DHUB_CMN_RES_R,
            cls.DHUB_SP_R,
            cls.DHUB_SP_U,
            cls.DHUB_W,
            cls.DHUB_XO_CUS_R,
            cls.DHUB_XO_ET_R,
            cls.DHUB_XOT_SUB_R,
            cls.DP_IM_R,
            cls.ENS_AM_A,
            cls.ENS_AM_R,
            cls.ENS_AM_TA,
            cls.ENS_AM_TR,
            cls.ENS_AM_VE,
            cls.ENS_AM_VS,
            cls.ENS_ATP_A,
            cls.ENS_ATP_R,
            cls.ENS_ATP_VS,
            cls.ENS_COMN_A,
            cls.ENS_COMN_R,
            cls.ENS_COMN_TA,
            cls.ENS_COMN_TR,
            cls.ENS_COMN_VS,
            cls.ENS_FW_A,
            cls.ENS_FW_R,
            cls.ENS_FW_VC,
            cls.ENS_FW_VP,
            cls.ENS_FW_VR,
            cls.ENS_FW_VS,
            cls.ENS_VRS_A,
            cls.ENS_VRS_R,
            cls.ENS_VRS_TA,
            cls.ENS_VRS_TR,
            cls.ENS_WP_A,
            cls.ENS_WP_R,
            cls.ENS_WP_TA,
            cls.ENS_WP_TR,
            cls.ENS_WP_VS,
            cls.EPO_ADIT_A,
            cls.EPO_ADIT_R,
            cls.EPO_ADMIN,
            cls.EPO_AGNT_D,
            cls.EPO_AGNT_W,
            cls.EPO_CDS_R,
            cls.EPO_DASH_P,
            cls.EPO_DASH_R,
            cls.EPO_DIR_A,
            cls.EPO_DXLC_A,
            cls.EPO_DXLC_R,
            cls.EPO_EAGT_A,
            cls.EPO_EAGT_R,
            cls.EPO_EAGT_TA,
            cls.EPO_EAGT_TR,
            cls.EPO_EVT_R,
            cls.EPO_PEVT_R,
            cls.EPO_PEVT_RP,
            cls.EPO_QERY_G,
            cls.EPO_QERY_U,
            cls.EPO_REG_TOKEN,
            cls.EPO_RESP_RA,
            cls.EPO_RESP_RU,
            cls.EPO_SDLR_E,
            cls.EPO_SDLR_R,
            cls.EPO_TAG_A,
            cls.EPO_TAGC_A,
            cls.EPO_TAGC_U,
            cls.EPO_TREE_M,
            cls.EPO_UBP_AE,
            cls.EPO_UBP_R,
            cls.FRP_ACT_R,
            cls.FRP_KEYS_R,
            cls.FRP_KEYS_X,
            cls.FRP_PO_R,
            cls.FRP_PO_X,
            cls.FRP_PROP_V,
            cls.INS_NOTI_R,
            cls.MI_USER_CONFIG,
            cls.MNE_ACT_R,
            cls.MNE_PO_A,
            cls.MNE_PO_R,
            cls.MNE_PROP_V,
            cls.MP_CMN_RES_R,
            cls.MP_CUS_R,
            cls.MP_SUB_R,
            cls.MP_SUB_W,
            cls.MP_XO_APP_R,
            cls.MP_XO_ET_R,
            cls.MVS_ENDP_A,
            cls.MVS_ENDP_R,
            cls.NDLP_CPO_A,
            cls.NDLP_CPO_R,
            cls.NDLP_DASH_R,
            cls.NDLP_PO_A,
            cls.NDLP_PO_R,
            cls.TKS_CK_R,
            cls.TKS_CK_X,
            cls.UAM_CC_R,
            cls.UAM_CC_W,
            cls.UDLP_CL_F,
            cls.UDLP_CL_M,
            cls.UDLP_CL_RD,
            cls.UDLP_CL_U,
            cls.UDLP_CL_V,
            cls.UDLP_DFN_F,
            cls.UDLP_DFN_U,
            cls.UDLP_DFN_V,
            cls.UDLP_DIS_F,
            cls.UDLP_DS_A,
            cls.UDLP_DS_BR,
            cls.UDLP_DS_G,
            cls.UDLP_HD_AMRK,
            cls.UDLP_HD_AOK,
            cls.UDLP_HD_ARQK,
            cls.UDLP_HD_AUK,
            cls.UDLP_IM_VF,
            cls.UDLP_IM_VM,
            cls.UDLP_IMDRL_F,
            cls.UDLP_IMDRS_F,
            cls.UDLP_IMDUM_F,
            cls.UDLP_OE_F,
            cls.UDLP_PC_V,
            cls.UDLP_PM_F,
            cls.UDLP_PM_TDSCVR,
            cls.UDLP_PM_TDT,
            cls.UDLP_PM_TDVC,
            cls.UDLP_PM_U,
            cls.UDLP_PM_V,
            cls.OPENID,
            cls.MV_M_ADMIN,
        }


class TrellixToken(BaseModel):
    """Model to work with auth token with additional info."""

    token: HttpToken

    scopes: Set[Scope]
    created_at: int

    def is_valid(self, scopes: List[Scope] | None = None) -> bool:
        """
        Check if token is not expired yet and valid for defined scopes.

        Returns:
            bool:
        """
        return not self.is_expired() and self.is_valid_for_scopes(scopes or [])

    def is_valid_for_scope(self, scope: Scope) -> bool:
        """
        Check if token is valid for defined scope.

        Returns:
            bool:
        """
        return scope in self.scopes

    def is_valid_for_scopes(self, scopes: List[Scope]) -> bool:
        """
        Check if token is valid for defined scopes.

        Returns:
            bool:
        """
        if scopes:
            return scopes == list(self.scopes)

        return True

    def is_expired(self) -> bool:
        """
        Check if token is expired.

        Returns:
            bool:
        """
        # Decrease time of expiration to avoid rate limiting problems
        return (self.created_at + self.token.expires_in) < (int(time()) - 1)
