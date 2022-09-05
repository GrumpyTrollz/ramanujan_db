from db import models
from db import ramanujan_db
from datetime import date,timedelta
import xlsxwriter as xl
import yagmail

sender_email = "ramanumachproj@gmail.com"
receivers_email  = ["yoni420@gmail.com","amirkl94@gmail.com"]
password = "Ramanujan123" # for documantation not used in the code


db_handle = ramanujan_db.RamanujanDB()

def getLastResults(model):
    today = date.today()
    yesterday = today - timedelta(days=1)
    return db_handle.session.query(model).filter(model.insertion_date > yesterday).all()

def write_const_results(sheet, results):
    sheet.write('A1','const symbols')
    sheet.write('B1','const descriptions')
    sheet.write('C1','cf numerator')
    sheet.write('D1','cf denominator')
    sheet.write('E1','connection type')
    sheet.write('F1','connection details')

    i=1
    for result in results:
        constants = db_handle.session.query(models.Constant).filter(models.Constant.constant_id.in_(result.constant_ids)).all()
        cf = db_handle.session.query(models.Cf).filter(models.Cf.cf_id == result.cf_id).one()
        assert(any(constants))
        assert(cf)
        sheet.write(i,0, str([constant.name for constant in constants]))
        sheet.write(i,1, str([constant.description for constant in constants]))
        sheet.write(i,2, str([int(x) for x in cf.partial_numerator]))
        sheet.write(i,3, str([int(x) for x in cf.partial_denominator]))
        sheet.write(i,4, result.connection_type)
        sheet.write(i,5, str(result.connection_details))
        i+=1
   

def write_cf_results(sheet, results):
    sheet.write('A1','source cf numenator')
    sheet.write('B1','source cf denominator')
    sheet.write('C1','target cf numenator')
    sheet.write('D1','target cf denominator')
    sheet.write('E1','connection type')
    sheet.write('F1','connection details')

    i=1
    for result in results:
        source_cf = db_handle.session.query(models.Cf).filter(models.Cf.cf_id == result.source_cf).one()
        target_cf = db_handle.session.query(models.Cf).filter(models.Cf.cf_id == result.target_cf).one()
        assert(source_cf)
        assert(target_cf)
        sheet.write(i,0, source_cf.partial_numerator)
        sheet.write(i,1, source_cf.partial_denominator)
        sheet.write(i,2, target_cf.partial_numerator)
        sheet.write(i,3, target_cf.partial_denominator)
        sheet.write(i,4, result.connection_type)
        sheet.write(i,5, result.connection_details)
        i+=1    


def send_summary(summary,xsl_file_name):

    yag = yagmail.SMTP(sender_email)
    for receiver in receivers_email:
        yag.send(
        to=receiver,
        subject="A day Summary from the Online Ramanujan machine",
        contents=summary, 
        attachments=xsl_file_name,
        )

def run_job(): 
    constants_results = getLastResults(models.CfMultiConstantConnection)
    cf_results = getLastResults(models.ContinuedFractionRelation)

    today_str = date.today().strftime("%d/%m/%Y")

    today_summary_excel = "summary "+ date.today().strftime("%d_%m_%Y")+ ".xlsx"

    workbook = xl.Workbook(today_summary_excel)
    if len(constants_results) > 0:
        const_sheet = workbook.add_worksheet("constants results")
        write_const_results(const_sheet,constants_results)
        
    if len(cf_results) > 0:
        cf_sheet = workbook.add_worksheet("cf results")
        write_cf_results(cf_sheet,cf_results)

    summary = "summary results for " + today_str + "\n"
    summary += "found total of " + str(len(constants_results)) + " constants relations.\n"
    summary += "found total of " + str(len(cf_results)) + " cf relations.\n"

    workbook.close()

    #send_summary(summary,today_summary_excel)
    # TODO the email doesn't work!!!

    #TODO: maybe put all excels results in a designated folder


