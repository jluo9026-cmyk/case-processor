# ============ 预设模板 ============

def _get_preset_template(preset_id: str):
    """获取预设模板"""
    return PRESET_TEMPLATES.get(preset_id)


PRESET_TEMPLATES = {
    'preset_1': {
        'id': 'preset_1',
        'name': '恒：王玉香案件调查报告',
        'type': 'preset',
        'description': '标准保险公估调查报告格式',
        'content': '''关于被保险人{{insured_name}}调查报告

一、案件基本情况
1、保险单内容
1）保 险 人：{{insurance_company}}
2）被保险人：{{insured_name}}
3）保 单 号：{{policy_no}}
4）保险期限：{{insurance_period}}
5）险    种：{{insurance_type}}
6）出险时间：{{accident_time}}

2、据案卷资料记载：{{case_description}}（见附件一）。

二、案件相关情况的核实
{{verification_items}}

（一）事故真实性的核实
{{investigation_content}}

1、调查员前往{{investigation_location_1}}{{investigation_content_1}}

2、调查员向{{interviewee}}做笔录，了解案件相关情况（见附件{{interview_attachment}}）。{{interview_content}}

3、调查员前往{{investigation_location_2}}了解案件相关情况（见附件{{location_attachment}}）。{{investigation_content_2}}

4、调查员前往{{investigation_location_3}}，向{{contact_person}}了解案件相关情况（见附件{{contact_attachment}}）。{{investigation_content_3}}

5、调查员前往{{investigation_location_4}}了解案件相关情况（见附件{{police_attachment}}）。{{police_investigation_content}}

6、调查员前往{{investigation_location_5}}调取{{medical_materials}}了解案件相关情况（见附件{{medical_attachment}}）。{{medical_investigation_content}}

7、调查员对{{insured_name}}的同业投保情况进行排查（见附件{{insurance_check_attachment}}）。{{insurance_check_content}}

8、后续，{{reporter}}向调查员提供了以下资料：
（1）{{insured_name}}身份证（见附件{{attachment_1}}）
（2）受益人身份证（见附件{{attachment_2}}）
（3）户口本（见附件{{attachment_3}}）
（4）接报警证明（见附件{{attachment_4}}）
（5）村委开具的死亡证明（见附件{{attachment_5}}）
（6）土葬证明和户籍注销证明（见附件{{attachment_6}}）
（7）索赔申请书（见附件{{attachment_7}}）
（8）情况声明（见附件{{attachment_8}}）
（9）直系亲属关系证明（见附件{{attachment_9}}）
（10）{{additional_document}}（见附件{{attachment_10}}）

综上，{{summary_conclusion}}

三、结论
1、{{conclusion_1}}
2、{{conclusion_2}}
3、{{conclusion_3}}
4、{{conclusion_4}}

以上报告供处理赔案时参考。

调查员：{{investigator}}
审核人：{{reviewer}}

{{company_name}}
{{report_date}}
''',
        'fields': [
            'insured_name', 'insurance_company', 'policy_no', 'insurance_period',
            'insurance_type', 'accident_time', 'case_description', 'verification_items',
            'investigation_content', 'investigation_location_1', 'investigation_content_1',
            'interviewee', 'interview_attachment', 'interview_content',
            'investigation_location_2', 'location_attachment', 'investigation_content_2',
            'investigation_location_3', 'contact_person', 'contact_attachment', 'investigation_content_3',
            'investigation_location_4', 'police_attachment', 'police_investigation_content',
            'investigation_location_5', 'medical_materials', 'medical_attachment', 'medical_investigation_content',
            'insurance_check_attachment', 'insurance_check_content',
            'reporter', 'attachment_1', 'attachment_2', 'attachment_3', 'attachment_4',
            'attachment_5', 'attachment_6', 'attachment_7', 'attachment_8', 'attachment_9',
            'attachment_10', 'additional_document',
            'summary_conclusion',
            'conclusion_1', 'conclusion_2', 'conclusion_3', 'conclusion_4',
            'investigator', 'reviewer', 'company_name', 'report_date'
        ]
    },
    'preset_2': {
        'id': 'preset_2',
        'name': '德：张锋身故案调查报告',
        'type': 'preset',
        'description': '张锋身故案调查报告格式',
        'content': '''被保险人{{insured_name}}身故案调查报告

{{case_date}}，接{{insurance_company}}委托，要求对{{policy_no}}号{{insurance_type}}保单项下被保险人{{insured_name}}于{{accident_time}}在{{accident_location}}案进行理赔调查（见附件一）。接案后我司委派工作人员就事故情况进行了调查核实，现秉承依法、独立、客观、公正的原则将调查情况报告如下：

一、保险合同主要内容（见附件二）
{{policies_detail}}

二、转案情况
{{case_description}}

三、事故真实性的调查与核实
{{investigation_content}}

四、事故原因及经过调查
{{accident_reason}}

五、事故调查重点及需要解决的问题
{{investigation_focus}}

综上，{{summary}}

六、保险责任分析
1、被保险人：{{liability_insured_name}}，与承保清单核实一致；
2、出险时间：{{liability_accident_time}}，在保险期限内；
3、出险地点：{{liability_accident_location}}；
4、出险原因：{{liability_accident_cause}}；
5、伤者身份：{{liability_victim_identity}}
6、保险责任：{{liability_content}}

七、调查结论
{{conclusion}}

八、声明
1、本报告是根据{{insurance_company}}的委托，依照《中华人民共和国保险法》等相关法律法规，结合本次事故适用的保险合同及核查的事实而作出的；
2、保险人提供的材料之真实性、完整性由保险人负责；
3、被保险人提供的材料之真实性、完整性由被保险人负责；
4、公估人仅对本报告的内容负责；
5、本报告仅作保险公估之用途。

以上报告仅供保险人作理赔参考。

主办公估员：{{investigator}}
授权签发：{{authorizer}}
协办公估员：{{assistant_investigator}}

{{company_name}}
{{report_date}}
''',
        'fields': [
            'insured_name', 'insurance_company', 'policy_no', 'insurance_type',
            'accident_time', 'accident_location', 'case_date', 'case_description',
            'policies_detail', 'investigation_content', 'accident_reason',
            'investigation_focus', 'summary', 'conclusion',
            'liability_insured_name', 'liability_accident_time', 'liability_accident_location',
            'liability_accident_cause', 'liability_victim_identity', 'liability_content',
            'investigator', 'authorizer', 'assistant_investigator',
            'company_name', 'report_date'
        ]
    },
    'preset_3': {
        'id': 'preset_3',
        'name': '旭：胡宝林案件调查报告',
        'type': 'preset',
        'description': '胡宝林身故案调查报告格式',
        'content': '''被保险人{{insured_name}}案身故案调查报告

{{case_date}}，接{{insurance_company}}委托，要求对{{policy_no}}号{{insurance_type}}保单项下被保险人{{insured_name}}于{{accident_time}}{{accident_description}}案进行理赔调查（见附件一）。接案后我司委派工作人员就事故情况进行了调查核实，现秉承依法、独立、客观、公正的原则将调查情况报告如下：

一、保险合同主要内容（见附件二）
1、险 种：{{insurance_type}}
2、保单号：{{policy_no}}
3、投保人：{{policy_holder}}
4、被保险人：{{insured_name}}（身份证：{{id_number}}）
5、保额：{{insurance_amount}}
6、保险期限：{{insurance_period}}
7、特别约定：{{special_agreements}}

二、转案情况
{{case_description}}

三、案件相关情况
{{investigation_content}}

综上，{{summary}}。

四、调查结论
{{conclusion}}

以上报告仅供保险人作理赔参考。

调查员：{{investigator}}
审核员：{{reviewer}}

{{company_name}}
{{report_date}}
''',
        'fields': [
            'insured_name', 'insurance_company', 'policy_no', 'insurance_type',
            'accident_time', 'accident_description', 'case_date', 'case_description',
            'policy_holder', 'id_number', 'insurance_amount', 'insurance_period',
            'special_agreements', 'investigation_content', 'summary', 'conclusion',
            'investigator', 'reviewer', 'company_name', 'report_date'
        ]
    }
}