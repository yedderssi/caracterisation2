#ifndef PERTESVSFREQ_H
#define PERTESVSFREQ_H

#include <QDialog>

namespace Ui {
class PertesVsFreq;
}

class PertesVsFreq : public QDialog
{
    Q_OBJECT

public:
    explicit PertesVsFreq(QWidget *parent = nullptr);
    ~PertesVsFreq();

private:
    Ui::PertesVsFreq *ui;
};

#endif // PERTESVSFREQ_H
